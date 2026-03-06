package thingsdb

type Task struct {
	UUID        string          `json:"uuid"`
	Type        string          `json:"type"`
	Title       string          `json:"title"`
	Status      string          `json:"status,omitempty"`
	Notes       string          `json:"notes,omitempty"`
	Start       string          `json:"start,omitempty"`
	StartDate   string          `json:"start_date,omitempty"`
	Deadline    string          `json:"deadline,omitempty"`
	StopDate    string          `json:"stop_date,omitempty"`
	Created     string          `json:"created,omitempty"`
	Modified    string          `json:"modified,omitempty"`
	Reminder    string          `json:"reminder_time,omitempty"`
	AreaUUID    string          `json:"area,omitempty"`
	AreaTitle   string          `json:"area_title,omitempty"`
	ProjectUUID string          `json:"project,omitempty"`
	ProjectName string          `json:"project_title,omitempty"`
	HeadingUUID string          `json:"heading,omitempty"`
	HeadingName string          `json:"heading_title,omitempty"`
	Trashed     bool            `json:"trashed,omitempty"`
	Index       int             `json:"index,omitempty"`
	TodayIndex  int             `json:"today_index,omitempty"`
	Tags        []string        `json:"tags,omitempty"`
	Checklist   []ChecklistItem `json:"checklist,omitempty"`
	Items       []Task          `json:"items,omitempty"`
}

type ChecklistItem struct {
	UUID     string `json:"uuid"`
	Type     string `json:"type"`
	Title    string `json:"title"`
	Status   string `json:"status,omitempty"`
	StopDate string `json:"stop_date,omitempty"`
	Created  string `json:"created,omitempty"`
	Modified string `json:"modified,omitempty"`
}

type Area struct {
	UUID  string   `json:"uuid"`
	Type  string   `json:"type"`
	Title string   `json:"title"`
	Tags  []string `json:"tags,omitempty"`
	Items []Task   `json:"items,omitempty"`
}

type Tag struct {
	UUID     string `json:"uuid"`
	Type     string `json:"type"`
	Title    string `json:"title"`
	Shortcut string `json:"shortcut,omitempty"`
	Items    []Task `json:"items,omitempty"`
}

type TaskFilter struct {
	Type               string
	Status             string
	Start              string
	Area               string
	Project            string
	Heading            string
	Tag                string
	StartDate          string
	StopDate           string
	Deadline           string
	DeadlineSuppressed *bool
	Trashed            *bool
	ContextTrashed     *bool
	Last               string
	LastStopDate       string
	SearchQuery        string
	Index              string
	CountOnly          bool
}

type SearchAdvancedFilter struct {
	Status    string
	StartDate string
	Deadline  string
	Tag       string
	Area      string
	Type      string
	Last      string
}
