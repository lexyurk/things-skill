package thingsurl

import (
	"fmt"
	"net/url"
	"sort"
	"strings"
)

func BuildURL(command string, params map[string]any) string {
	values := url.Values{}

	keys := make([]string, 0, len(params))
	for key := range params {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	for _, key := range keys {
		value := params[key]
		if value == nil {
			continue
		}
		switch v := value.(type) {
		case bool:
			values.Set(key, strings.ToLower(fmt.Sprintf("%t", v)))
		case []string:
			if len(v) == 0 {
				continue
			}
			values.Set(key, strings.Join(v, ","))
		default:
			text := fmt.Sprintf("%v", v)
			if text == "" {
				continue
			}
			values.Set(key, text)
		}
	}

	if len(values) == 0 {
		return fmt.Sprintf("things:///%s", command)
	}
	encoded := strings.ReplaceAll(values.Encode(), "+", "%20")
	return fmt.Sprintf("things:///%s?%s", command, encoded)
}

type AddTodoInput struct {
	Title          string
	Notes          string
	When           string
	Deadline       string
	Tags           []string
	ChecklistItems []string
	ListID         string
	ListTitle      string
	Heading        string
	HeadingID      string
}

func AddTodoURL(in AddTodoInput) string {
	params := map[string]any{
		"title":           in.Title,
		"notes":           in.Notes,
		"when":            in.When,
		"deadline":        in.Deadline,
		"tags":            in.Tags,
		"checklist-items": strings.Join(in.ChecklistItems, "\n"),
		"list-id":         in.ListID,
		"list":            in.ListTitle,
		"heading":         in.Heading,
		"heading-id":      in.HeadingID,
	}
	return BuildURL("add", params)
}

type AddProjectInput struct {
	Title     string
	Notes     string
	When      string
	Deadline  string
	Tags      []string
	AreaID    string
	AreaTitle string
	Todos     []string
}

func AddProjectURL(in AddProjectInput) string {
	params := map[string]any{
		"title":    in.Title,
		"notes":    in.Notes,
		"when":     in.When,
		"deadline": in.Deadline,
		"tags":     in.Tags,
		"area-id":  in.AreaID,
		"area":     in.AreaTitle,
		"to-dos":   strings.Join(in.Todos, "\n"),
	}
	return BuildURL("add-project", params)
}

type UpdateTodoInput struct {
	ID        string
	AuthToken string
	Title     string
	Notes     string
	When      string
	Deadline  string
	Tags      []string
	Completed *bool
	Canceled  *bool
	List      string
	ListID    string
	Heading   string
	HeadingID string
}

func UpdateTodoURL(in UpdateTodoInput) string {
	params := map[string]any{
		"id":         in.ID,
		"auth-token": in.AuthToken,
		"title":      in.Title,
		"notes":      in.Notes,
		"when":       in.When,
		"deadline":   in.Deadline,
		"tags":       in.Tags,
		"list":       in.List,
		"list-id":    in.ListID,
		"heading":    in.Heading,
		"heading-id": in.HeadingID,
	}
	if in.Completed != nil {
		params["completed"] = *in.Completed
	}
	if in.Canceled != nil {
		params["canceled"] = *in.Canceled
	}
	return BuildURL("update", params)
}

type UpdateProjectInput struct {
	ID        string
	AuthToken string
	Title     string
	Notes     string
	When      string
	Deadline  string
	Tags      []string
	Completed *bool
	Canceled  *bool
}

func UpdateProjectURL(in UpdateProjectInput) string {
	params := map[string]any{
		"id":         in.ID,
		"auth-token": in.AuthToken,
		"title":      in.Title,
		"notes":      in.Notes,
		"when":       in.When,
		"deadline":   in.Deadline,
		"tags":       in.Tags,
	}
	if in.Completed != nil {
		params["completed"] = *in.Completed
	}
	if in.Canceled != nil {
		params["canceled"] = *in.Canceled
	}
	return BuildURL("update-project", params)
}

func ShowURL(id string, query string, filterTags []string) string {
	return BuildURL("show", map[string]any{
		"id":     id,
		"query":  query,
		"filter": filterTags,
	})
}

func SearchURL(query string) string {
	return BuildURL("search", map[string]any{"query": query})
}

func JSONURL(data string, authToken string, reveal *bool) string {
	params := map[string]any{
		"data":       data,
		"auth-token": authToken,
	}
	if reveal != nil {
		params["reveal"] = *reveal
	}
	return BuildURL("json", params)
}
