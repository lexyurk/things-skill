package thingsdb

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var dateMatcher = regexp.MustCompile(`^(=|==|<|<=|>|>=)?(\d{4}-\d{2}-\d{2})$`)

var startValueToInt = map[string]int{
	"inbox":   0,
	"anytime": 1,
	"someday": 2,
}

var statusValueToInt = map[string]int{
	"incomplete": 0,
	"canceled":   2,
	"completed":  3,
}

var typeValueToInt = map[string]int{
	"to-do":   0,
	"project": 1,
	"heading": 2,
}

func thingsDateTodaySQL() string {
	return "((strftime('%Y', date('now', 'localtime')) << 16) | (strftime('%m', date('now', 'localtime')) << 12) | (strftime('%d', date('now', 'localtime')) << 7))"
}

func thingsDateToISOExpr(column string) string {
	return fmt.Sprintf(
		"CASE WHEN %[1]s THEN printf('%%d-%%02d-%%02d', (%[1]s & 134152192) >> 16, (%[1]s & 61440) >> 12, (%[1]s & 3968) >> 7) ELSE NULL END",
		column,
	)
}

func thingsTimeToISOExpr(column string) string {
	return fmt.Sprintf(
		"CASE WHEN %[1]s THEN printf('%%02d:%%02d', (%[1]s & 2080374784) >> 26, (%[1]s & 66060288) >> 20) ELSE NULL END",
		column,
	)
}

func isoDateToThingsDate(value string) (int, error) {
	t, err := time.Parse("2006-01-02", value)
	if err != nil {
		return 0, err
	}
	return (t.Year() << 16) | (int(t.Month()) << 12) | (t.Day() << 7), nil
}

func parseLastOffset(period string) (string, error) {
	if len(period) < 2 {
		return "", ErrInvalidOffset
	}
	unit := period[len(period)-1]
	numText := period[:len(period)-1]
	n, err := strconv.Atoi(numText)
	if err != nil || n < 0 {
		return "", ErrInvalidOffset
	}

	switch unit {
	case 'd':
		return fmt.Sprintf("-%d days", n), nil
	case 'w':
		return fmt.Sprintf("-%d days", n*7), nil
	case 'm':
		return fmt.Sprintf("-%d months", n), nil
	case 'y':
		return fmt.Sprintf("-%d years", n), nil
	default:
		return "", ErrInvalidOffset
	}
}

func appendThingsDateFilter(conditions *[]string, args *[]any, column string, value string) error {
	if value == "" {
		return nil
	}

	switch value {
	case "true":
		*conditions = append(*conditions, fmt.Sprintf("%s IS NOT NULL", column))
		return nil
	case "false":
		*conditions = append(*conditions, fmt.Sprintf("%s IS NULL", column))
		return nil
	case "future":
		*conditions = append(*conditions, fmt.Sprintf("%s > %s", column, thingsDateTodaySQL()))
		return nil
	case "past":
		*conditions = append(*conditions, fmt.Sprintf("%s <= %s", column, thingsDateTodaySQL()))
		return nil
	}

	matches := dateMatcher.FindStringSubmatch(value)
	if len(matches) == 0 {
		return fmt.Errorf("invalid date filter: %s", value)
	}
	op := matches[1]
	if op == "" {
		op = "=="
	}
	thingsDate, err := isoDateToThingsDate(matches[2])
	if err != nil {
		return err
	}
	*conditions = append(*conditions, fmt.Sprintf("%s %s ?", column, op))
	*args = append(*args, thingsDate)
	return nil
}

func appendUnixDateFilter(conditions *[]string, args *[]any, column string, value string) error {
	if value == "" {
		return nil
	}
	switch value {
	case "true":
		*conditions = append(*conditions, fmt.Sprintf("%s IS NOT NULL", column))
		return nil
	case "false":
		*conditions = append(*conditions, fmt.Sprintf("%s IS NULL", column))
		return nil
	case "future":
		*conditions = append(*conditions, fmt.Sprintf("date(%s, 'unixepoch', 'localtime') > date('now', 'localtime')", column))
		return nil
	case "past":
		*conditions = append(*conditions, fmt.Sprintf("date(%s, 'unixepoch', 'localtime') <= date('now', 'localtime')", column))
		return nil
	}

	matches := dateMatcher.FindStringSubmatch(value)
	if len(matches) == 0 {
		return fmt.Errorf("invalid unix date filter: %s", value)
	}
	op := matches[1]
	if op == "" {
		op = "=="
	}
	*conditions = append(*conditions, fmt.Sprintf("date(%s, 'unixepoch', 'localtime') %s date(?)", column, op))
	*args = append(*args, matches[2])
	return nil
}

func buildTaskQuery(filter TaskFilter) (string, []any, error) {
	indexColumn := filter.Index
	if indexColumn == "" {
		indexColumn = "index"
	}
	if indexColumn != "index" && indexColumn != "todayIndex" {
		return "", nil, fmt.Errorf("invalid index column %q", indexColumn)
	}

	conditions := []string{
		"TASK.rt1_recurrenceRule IS NULL",
	}
	args := make([]any, 0, 16)

	if filter.UUID != "" {
		conditions = append(conditions, "TASK.uuid = ?")
		args = append(args, filter.UUID)
	}

	if filter.Trashed != nil {
		if *filter.Trashed {
			conditions = append(conditions, "TASK.trashed = 1")
		} else {
			conditions = append(conditions, "TASK.trashed = 0")
		}
	}

	if filter.ContextTrashed != nil {
		if *filter.ContextTrashed {
			conditions = append(conditions, "(COALESCE(PROJECT.trashed, 0) = 1 OR COALESCE(PROJECT_OF_HEADING.trashed, 0) = 1)")
		} else {
			conditions = append(conditions, "COALESCE(PROJECT.trashed, 0) = 0")
			conditions = append(conditions, "COALESCE(PROJECT_OF_HEADING.trashed, 0) = 0")
		}
	}

	if filter.Type != "" {
		taskType, ok := typeValueToInt[filter.Type]
		if !ok {
			return "", nil, fmt.Errorf("invalid type value %q", filter.Type)
		}
		conditions = append(conditions, "TASK.type = ?")
		args = append(args, taskType)
	}

	if filter.Start != "" {
		startValue, ok := startValueToInt[strings.ToLower(filter.Start)]
		if !ok {
			return "", nil, fmt.Errorf("invalid start value %q", filter.Start)
		}
		conditions = append(conditions, "TASK.start = ?")
		args = append(args, startValue)
	}

	if filter.Status != "" {
		statusValue, ok := statusValueToInt[filter.Status]
		if !ok {
			return "", nil, fmt.Errorf("invalid status value %q", filter.Status)
		}
		conditions = append(conditions, "TASK.status = ?")
		args = append(args, statusValue)
	}

	if filter.Area != "" {
		conditions = append(conditions, "TASK.area = ?")
		args = append(args, filter.Area)
	}

	if filter.Project != "" {
		conditions = append(conditions, "(TASK.project = ? OR PROJECT_OF_HEADING.uuid = ?)")
		args = append(args, filter.Project, filter.Project)
	}

	if filter.Heading != "" {
		conditions = append(conditions, "TASK.heading = ?")
		args = append(args, filter.Heading)
	}

	if filter.DeadlineSuppressed != nil {
		if *filter.DeadlineSuppressed {
			conditions = append(conditions, "TASK.deadlineSuppressionDate IS NOT NULL")
		} else {
			conditions = append(conditions, "TASK.deadlineSuppressionDate IS NULL")
		}
	}

	if filter.Tag != "" {
		conditions = append(conditions, "TAG.title = ?")
		args = append(args, filter.Tag)
	}

	if err := appendThingsDateFilter(&conditions, &args, "TASK.startDate", filter.StartDate); err != nil {
		return "", nil, err
	}
	if err := appendUnixDateFilter(&conditions, &args, "TASK.stopDate", filter.StopDate); err != nil {
		return "", nil, err
	}
	if err := appendThingsDateFilter(&conditions, &args, "TASK.deadline", filter.Deadline); err != nil {
		return "", nil, err
	}

	if filter.Last != "" {
		modifier, err := parseLastOffset(filter.Last)
		if err != nil {
			return "", nil, err
		}
		conditions = append(conditions, "datetime(TASK.creationDate, 'unixepoch', 'localtime') > datetime('now', ?)")
		args = append(args, modifier)
	}

	if filter.LastStopDate != "" {
		modifier, err := parseLastOffset(filter.LastStopDate)
		if err != nil {
			return "", nil, err
		}
		conditions = append(conditions, "datetime(TASK.stopDate, 'unixepoch', 'localtime') > datetime('now', ?)")
		args = append(args, modifier)
	}

	if filter.SearchQuery != "" {
		like := "%" + filter.SearchQuery + "%"
		conditions = append(conditions, "(TASK.title LIKE ? OR TASK.notes LIKE ? OR AREA.title LIKE ?)")
		args = append(args, like, like, like)
	}

	query := fmt.Sprintf(`
SELECT DISTINCT
	TASK.uuid,
	CASE
		WHEN TASK.type = 0 THEN 'to-do'
		WHEN TASK.type = 1 THEN 'project'
		WHEN TASK.type = 2 THEN 'heading'
	END AS type,
	CASE WHEN TASK.trashed = 1 THEN 1 ELSE 0 END AS trashed,
	TASK.title,
	CASE
		WHEN TASK.status = 0 THEN 'incomplete'
		WHEN TASK.status = 2 THEN 'canceled'
		WHEN TASK.status = 3 THEN 'completed'
	END AS status,
	CASE WHEN AREA.uuid IS NOT NULL THEN AREA.uuid END AS area,
	CASE WHEN AREA.uuid IS NOT NULL THEN AREA.title END AS area_title,
	CASE WHEN PROJECT.uuid IS NOT NULL THEN PROJECT.uuid END AS project,
	CASE WHEN PROJECT.uuid IS NOT NULL THEN PROJECT.title END AS project_title,
	CASE WHEN HEADING.uuid IS NOT NULL THEN HEADING.uuid END AS heading,
	CASE WHEN HEADING.uuid IS NOT NULL THEN HEADING.title END AS heading_title,
	TASK.notes,
	CASE WHEN TAG.uuid IS NOT NULL THEN 1 ELSE 0 END AS has_tags,
	CASE
		WHEN TASK.start = 0 THEN 'Inbox'
		WHEN TASK.start = 1 THEN 'Anytime'
		WHEN TASK.start = 2 THEN 'Someday'
	END AS start,
	CASE WHEN CHECKLIST_ITEM.uuid IS NOT NULL THEN 1 ELSE 0 END AS has_checklist,
	%s AS start_date,
	%s AS deadline,
	%s AS reminder_time,
	datetime(TASK.stopDate, 'unixepoch', 'localtime') AS stop_date,
	datetime(TASK.creationDate, 'unixepoch', 'localtime') AS created,
	datetime(TASK.userModificationDate, 'unixepoch', 'localtime') AS modified,
	TASK."index",
	TASK.todayIndex
FROM TMTask TASK
LEFT JOIN TMTask PROJECT ON TASK.project = PROJECT.uuid
LEFT JOIN TMArea AREA ON TASK.area = AREA.uuid
LEFT JOIN TMTask HEADING ON TASK.heading = HEADING.uuid
LEFT JOIN TMTask PROJECT_OF_HEADING ON HEADING.project = PROJECT_OF_HEADING.uuid
LEFT JOIN TMTaskTag TAGS ON TASK.uuid = TAGS.tasks
LEFT JOIN TMTag TAG ON TAGS.tags = TAG.uuid
LEFT JOIN TMChecklistItem CHECKLIST_ITEM ON TASK.uuid = CHECKLIST_ITEM.task
WHERE %s
ORDER BY TASK."%s"
`,
		thingsDateToISOExpr("TASK.startDate"),
		thingsDateToISOExpr("TASK.deadline"),
		thingsTimeToISOExpr("TASK.reminderTime"),
		strings.Join(conditions, " AND "),
		indexColumn,
	)

	return query, args, nil
}
