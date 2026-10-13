package cli

import (
	"os"

	"github.com/lexyurk/things-skill/internal/cloud"
	"github.com/spf13/cobra"
)

func (a *app) addCloudCommands(root *cobra.Command) {
	var python, dataDir string
	root.PersistentFlags().StringVar(&python, "cloud-python", os.Getenv("THINGS_CLOUD_PYTHON"), "Python 3.9+ executable for Things Cloud")
	root.PersistentFlags().StringVar(&dataDir, "cloud-data-dir", os.Getenv("THINGS_CLOUD_DATA_DIR"), "Private Things Cloud state directory")
	client := func() cloud.Client { return cloud.Client{Python: python, DataDir: dataDir} }
	root.AddCommand(&cobra.Command{
		Use:   "serve",
		Short: "Run the Things Cloud MCP server over stdio (Linux or macOS)",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return client().Run(cmd.Context(), []string{"serve"}, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
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
			return client().Run(cmd.Context(), args, cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr())
		},
	})
}
