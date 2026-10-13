package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/lexyurk/things-skill/internal/cloud"
	"github.com/lexyurk/things-skill/internal/thingsdb"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

func (a *app) cloudClient() cloud.Client {
	return cloud.Client{Python: a.cloudPython, DataDir: a.cloudDataDir}
}

func (a *app) addCloudCommands(root *cobra.Command) {
	root.PersistentFlags().StringVar(&a.cloudPython, "cloud-python", os.Getenv("THINGS_CLOUD_PYTHON"), "Python 3.9+ executable for Things Cloud")
	root.PersistentFlags().StringVar(&a.cloudDataDir, "cloud-data-dir", os.Getenv("THINGS_CLOUD_DATA_DIR"), "Private Things Cloud state directory")
	root.PersistentFlags().StringVar(&a.backend, "backend", "auto", "Task backend: auto, cloud, or local (macOS SQLite/URLs)")
	var email, envFile string
	login := &cobra.Command{
		Use: "login", Short: "Log in to Things Cloud; prompt for a hidden password and persist account access",
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			args := []string{"connect"}
			if email != "" {
				args = append(args, "--email", email)
			}
			if envFile != "" {
				args = append(args, "--env-file", envFile)
			}
			return a.cloudClient().Run(cmd.Context(), args, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
		},
	}
	login.Flags().StringVar(&email, "email", "", "Things Cloud email (otherwise prompted)")
	login.Flags().StringVar(&envFile, "env-file", "", "Owner-only .env containing USERNAME and PASSWORD")
	root.AddCommand(login)
	for _, pair := range [][2]string{{"logout", "disconnect"}, {"status", "status"}, {"sync", "sync"}} {
		name, operation := pair[0], pair[1]
		root.AddCommand(&cobra.Command{Use: name, Short: "Things Cloud " + name, Args: cobra.NoArgs,
			RunE: func(cmd *cobra.Command, _ []string) error {
				return a.cloudClient().Run(cmd.Context(), []string{operation}, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
			},
		})
	}
	root.AddCommand(&cobra.Command{
		Use:   "serve",
		Short: "Run the Things Cloud MCP server over stdio (Linux or macOS)",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return a.cloudClient().Run(cmd.Context(), []string{"serve"}, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
		},
	})
	root.AddCommand(&cobra.Command{
		Use:                "cloud [command] [arguments...]",
		Short:              "Run cloud task commands, login, sync, or any MCP tool",
		DisableFlagParsing: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 {
				args = []string{"--help"}
			}
			return a.cloudClient().Run(cmd.Context(), args, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
		},
	})
}

func (a *app) useCloud() (bool, error) {
	switch a.backend {
	case "cloud":
		if a.dryRun || a.dbPath != "" {
			return false, fmt.Errorf("--backend cloud cannot be combined with --dry-run or --db-path")
		}
		return true, nil
	case "local":
		return false, nil
	case "auto":
		if a.dryRun || a.dbPath != "" || os.Getenv("THINGSDB") != "" {
			return false, nil
		}
		if runtime.GOOS != "darwin" {
			return true, nil
		}
		directory := a.cloudDataDir
		if directory == "" {
			base := os.Getenv("XDG_DATA_HOME")
			if base == "" {
				home, err := os.UserHomeDir()
				if err != nil {
					return false, err
				}
				base = filepath.Join(home, ".local", "share")
			}
			directory = filepath.Join(base, "things-cloud-plugin")
		}
		_, err := os.Lstat(filepath.Join(directory, "account.json"))
		if err != nil && !os.IsNotExist(err) {
			return false, fmt.Errorf("cannot inspect Things Cloud login: %w", err)
		}
		return err == nil, nil
	default:
		return false, fmt.Errorf("--backend must be auto, cloud, or local")
	}
}

// Keep the existing command/flag contract. Send parsed flags over stdin to the
// shared cloud adapter; task text never becomes shell code or process arguments.
func (a *app) routeCloudCommands(root *cobra.Command) {
	var walk func(*cobra.Command, []string)
	walk = func(command *cobra.Command, path []string) {
		if command != root {
			path = append(append([]string{}, path...), command.Name())
		}
		for _, child := range command.Commands() {
			walk(child, path)
		}
		if command.RunE == nil || len(path) == 0 {
			return
		}
		switch path[0] {
		case "login", "logout", "status", "sync", "cloud", "serve", "help", "completion":
			return
		}
		if path[0] == "todo" || path[0] == "project" {
			command.Flags().String("request-id", "", "Stable cloud write ID; reuse the same ID when recovering a partial command")
		}
		original := command.RunE
		command.RunE = func(cmd *cobra.Command, args []string) error {
			use, err := a.useCloud()
			if err != nil {
				return err
			}
			if !use {
				return original(cmd, args)
			}
			flags := map[string]any{}
			cmd.Flags().VisitAll(func(flag *pflag.Flag) {
				if flag.Name == "help" {
					return
				}
				switch flag.Value.Type() {
				case "bool":
					value, _ := cmd.Flags().GetBool(flag.Name)
					flags[flag.Name] = value
				case "int":
					value, _ := cmd.Flags().GetInt(flag.Name)
					flags[flag.Name] = value
				case "stringSlice":
					value, _ := cmd.Flags().GetStringSlice(flag.Name)
					flags[flag.Name] = value
				default:
					flags[flag.Name] = flag.Value.String()
				}
			})
			changed := []string{}
			cmd.Flags().Visit(func(flag *pflag.Flag) { changed = append(changed, flag.Name) })
			body, err := json.Marshal(map[string]any{"command": path, "args": args, "flags": flags, "changed": changed})
			if err != nil {
				return err
			}
			var output bytes.Buffer
			runErr := a.cloudClient().Run(cmd.Context(), []string{"compat"}, bytes.NewReader(body), &output, cmd.ErrOrStderr())
			if output.Len() == 0 && runErr != nil {
				return runErr
			}
			var response struct {
				Kind    string
				Data    json.RawMessage
				Message string
			}
			if err := json.Unmarshal(output.Bytes(), &response); err != nil {
				return fmt.Errorf("invalid cloud adapter response")
			}
			switch response.Kind {
			case "tasks":
				var tasks []thingsdb.Task
				if err := json.Unmarshal(response.Data, &tasks); err != nil {
					return err
				}
				return a.printTasks(tasks)
			case "areas":
				var areas []thingsdb.Area
				if err := json.Unmarshal(response.Data, &areas); err != nil {
					return err
				}
				return a.printAreas(areas)
			case "tags":
				var tags []thingsdb.Tag
				if err := json.Unmarshal(response.Data, &tags); err != nil {
					return err
				}
				return a.printTags(tags)
			case "result":
				if err := a.printResult(response.Data, response.Message); err != nil {
					return err
				}
				return runErr
			default:
				return fmt.Errorf("unknown cloud adapter response kind %q", strings.TrimSpace(response.Kind))
			}
		}
	}
	walk(root, nil)
}
