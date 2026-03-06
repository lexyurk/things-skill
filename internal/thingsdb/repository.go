package thingsdb

import (
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"path/filepath"
	"sort"
	"strings"

	_ "modernc.org/sqlite"
)

const authTokenRowUUID = "RhAzEf6qDxCD5PmnZVtBZR"

type Repository struct {
	db   *sql.DB
	path string
}

func Open(dbPathOverride string) (*Repository, error) {
	path, err := ResolveDBPath(dbPathOverride)
	if err != nil {
		return nil, err
	}
	return OpenPath(path)
}

func OpenPath(path string) (*Repository, error) {
	dsn := sqliteReadOnlyDSN(path)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, err
	}

	return &Repository{db: db, path: path}, nil
}

func sqliteReadOnlyDSN(path string) string {
	if !filepath.IsAbs(path) {
		absPath, err := filepath.Abs(path)
		if err == nil {
			path = absPath
		}
	}

	query := url.Values{}
	query.Set("mode", "ro")

	return (&url.URL{
		Scheme:   "file",
		Path:     path,
		RawQuery: query.Encode(),
	}).String()
}

func (r *Repository) Close() error {
	if r == nil || r.db == nil {
		return nil
	}
	return r.db.Close()
}

func boolPtr(v bool) *bool {
	return &v
}

func nullToString(v sql.NullString) string {
	if v.Valid {
		return v.String
	}
	return ""
}

func nullToInt(v sql.NullInt64) int {
	if v.Valid {
		return int(v.Int64)
	}
	return 0
}

func (r *Repository) checklistCreatedExpr() (string, error) {
	rows, err := r.db.Query(`PRAGMA table_info(TMChecklistItem)`)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	for rows.Next() {
		var (
			columnID   int
			columnName string
			columnType string
			notNull    int
			defaultVal sql.NullString
			primaryKey int
		)
		if err := rows.Scan(&columnID, &columnName, &columnType, &notNull, &defaultVal, &primaryKey); err != nil {
			return "", err
		}
		if columnName == "creationDate" {
			return "datetime(CHECKLIST_ITEM.creationDate, 'unixepoch', 'localtime')", nil
		}
	}
	if err := rows.Err(); err != nil {
		return "", err
	}

	return "datetime(CHECKLIST_ITEM.userModificationDate, 'unixepoch', 'localtime')", nil
}

func defaultTaskFilter(filter TaskFilter) TaskFilter {
	if filter.Status == "" {
		filter.Status = "incomplete"
	}
	if filter.Trashed == nil {
		filter.Trashed = boolPtr(false)
	}
	if filter.ContextTrashed == nil {
		filter.ContextTrashed = boolPtr(false)
	}
	return filter
}

func (r *Repository) queryTasks(filter TaskFilter, includeItems bool) ([]Task, error) {
	query, args, err := buildTaskQuery(filter)
	if err != nil {
		return nil, err
	}

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	tasks := make([]Task, 0, 64)
	for rows.Next() {
		var (
			uuid         string
			itemType     string
			trashedInt   int
			title        string
			status       sql.NullString
			areaUUID     sql.NullString
			areaTitle    sql.NullString
			projectUUID  sql.NullString
			projectTitle sql.NullString
			headingUUID  sql.NullString
			headingTitle sql.NullString
			notes        sql.NullString
			hasTags      int
			start        sql.NullString
			hasChecklist int
			startDate    sql.NullString
			deadline     sql.NullString
			reminder     sql.NullString
			stopDate     sql.NullString
			created      sql.NullString
			modified     sql.NullString
			index        sql.NullInt64
			todayIndex   sql.NullInt64
		)

		if err := rows.Scan(
			&uuid,
			&itemType,
			&trashedInt,
			&title,
			&status,
			&areaUUID,
			&areaTitle,
			&projectUUID,
			&projectTitle,
			&headingUUID,
			&headingTitle,
			&notes,
			&hasTags,
			&start,
			&hasChecklist,
			&startDate,
			&deadline,
			&reminder,
			&stopDate,
			&created,
			&modified,
			&index,
			&todayIndex,
		); err != nil {
			return nil, err
		}

		task := Task{
			UUID:        uuid,
			Type:        itemType,
			Title:       title,
			Status:      nullToString(status),
			Notes:       nullToString(notes),
			Start:       nullToString(start),
			StartDate:   nullToString(startDate),
			Deadline:    nullToString(deadline),
			StopDate:    nullToString(stopDate),
			Created:     nullToString(created),
			Modified:    nullToString(modified),
			Reminder:    nullToString(reminder),
			AreaUUID:    nullToString(areaUUID),
			AreaTitle:   nullToString(areaTitle),
			ProjectUUID: nullToString(projectUUID),
			ProjectName: nullToString(projectTitle),
			HeadingUUID: nullToString(headingUUID),
			HeadingName: nullToString(headingTitle),
			Trashed:     trashedInt == 1,
			Index:       nullToInt(index),
			TodayIndex:  nullToInt(todayIndex),
		}

		if hasTags == 1 {
			task.Tags, err = r.TagsOfTask(task.UUID)
			if err != nil {
				return nil, err
			}
		}

		if includeItems {
			switch task.Type {
			case "to-do":
				if hasChecklist == 1 {
					task.Checklist, err = r.ChecklistItems(task.UUID)
					if err != nil {
						return nil, err
					}
				}
			case "project":
				task.Items, err = r.projectItems(task.UUID)
				if err != nil {
					return nil, err
				}
				sort.SliceStable(task.Items, func(i, j int) bool {
					return task.Items[i].Type > task.Items[j].Type
				})
			case "heading":
				task.Items, err = r.Todos("", true, task.UUID)
				if err != nil {
					return nil, err
				}
			}
		}

		tasks = append(tasks, task)
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}
	return tasks, nil
}

func (r *Repository) projectItems(projectUUID string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Project:        projectUUID,
		ContextTrashed: nil,
	})
	return r.queryTasks(filter, true)
}

func (r *Repository) Tasks(filter TaskFilter, includeItems bool) ([]Task, error) {
	return r.queryTasks(defaultTaskFilter(filter), includeItems)
}

func (r *Repository) Todos(projectUUID string, includeItems bool, headingUUID string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Type:    "to-do",
		Project: projectUUID,
		Heading: headingUUID,
	})
	return r.queryTasks(filter, includeItems)
}

func (r *Repository) Projects(includeItems bool) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Type: "project",
	})
	return r.queryTasks(filter, includeItems)
}

func (r *Repository) Headings(projectUUID string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Type:    "heading",
		Project: projectUUID,
	})
	return r.queryTasks(filter, false)
}

func (r *Repository) Search(query string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		SearchQuery: query,
	})
	return r.queryTasks(filter, true)
}

func (r *Repository) SearchAdvanced(filter SearchAdvancedFilter) ([]Task, error) {
	taskFilter := defaultTaskFilter(TaskFilter{
		Status:    strings.ToLower(filter.Status),
		StartDate: strings.ToLower(filter.StartDate),
		Deadline:  strings.ToLower(filter.Deadline),
		Tag:       filter.Tag,
		Area:      filter.Area,
		Last:      strings.ToLower(filter.Last),
	})
	if filter.Type != "" {
		taskFilter.Type = strings.ToLower(filter.Type)
		return r.queryTasks(taskFilter, true)
	}
	taskFilter.Type = "to-do"
	return r.queryTasks(taskFilter, true)
}

func (r *Repository) Recent(period string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Last: strings.ToLower(period),
	})
	return r.queryTasks(filter, true)
}

func (r *Repository) Inbox() ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{Start: "Inbox"})
	return r.queryTasks(filter, true)
}

func (r *Repository) Anytime() ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{Start: "Anytime"})
	tasks, err := r.queryTasks(filter, true)
	if err != nil {
		return nil, err
	}
	return r.FilterSomedayProjectTasks(tasks)
}

func (r *Repository) Upcoming() ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Start:     "Someday",
		StartDate: "future",
	})
	tasks, err := r.queryTasks(filter, true)
	if err != nil {
		return nil, err
	}
	return r.FilterSomedayProjectTasks(tasks)
}

func (r *Repository) Today() ([]Task, error) {
	regular, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		Start:     "Anytime",
		StartDate: "true",
		Index:     "todayIndex",
	}), true)
	if err != nil {
		return nil, err
	}
	unconfirmedScheduled, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		Start:     "Someday",
		StartDate: "past",
		Index:     "todayIndex",
	}), true)
	if err != nil {
		return nil, err
	}
	deadlineSuppressed := false
	unconfirmedOverdue, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		StartDate:          "false",
		Deadline:           "past",
		DeadlineSuppressed: &deadlineSuppressed,
	}), true)
	if err != nil {
		return nil, err
	}
	all := append(regular, unconfirmedScheduled...)
	all = append(all, unconfirmedOverdue...)
	sort.SliceStable(all, func(i, j int) bool {
		if all[i].TodayIndex == all[j].TodayIndex {
			return all[i].StartDate < all[j].StartDate
		}
		return all[i].TodayIndex < all[j].TodayIndex
	})
	return r.FilterSomedayProjectTasks(all)
}

func (r *Repository) Someday() ([]Task, error) {
	base, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		Start:     "Someday",
		StartDate: "false",
	}), true)
	if err != nil {
		return nil, err
	}
	somedayProjectIDs, headingToProject, err := r.GetSomedayContext()
	if err != nil {
		return nil, err
	}
	if len(somedayProjectIDs) == 0 {
		return base, nil
	}

	anytime, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		Start: "Anytime",
	}), true)
	if err != nil {
		return nil, err
	}

	seen := make(map[string]struct{}, len(base))
	for _, task := range base {
		seen[task.UUID] = struct{}{}
	}
	for _, task := range anytime {
		if r.IsInSomedayProject(task, somedayProjectIDs, headingToProject) {
			if _, ok := seen[task.UUID]; ok {
				continue
			}
			base = append(base, task)
			seen[task.UUID] = struct{}{}
		}
	}
	return base, nil
}

func (r *Repository) Logbook() ([]Task, error) {
	completed, err := r.queryTasks(TaskFilter{
		Status:         "completed",
		Trashed:        boolPtr(false),
		ContextTrashed: boolPtr(false),
	}, true)
	if err != nil {
		return nil, err
	}
	canceled, err := r.queryTasks(TaskFilter{
		Status:         "canceled",
		Trashed:        boolPtr(false),
		ContextTrashed: boolPtr(false),
	}, true)
	if err != nil {
		return nil, err
	}
	all := append(completed, canceled...)
	sort.SliceStable(all, func(i, j int) bool {
		return all[i].StopDate > all[j].StopDate
	})
	return all, nil
}

func (r *Repository) Trash() ([]Task, error) {
	return r.queryTasks(TaskFilter{
		Status:         "",
		Trashed:        boolPtr(true),
		ContextTrashed: nil,
	}, true)
}

func (r *Repository) Areas(includeItems bool) ([]Area, error) {
	rows, err := r.db.Query(`
SELECT DISTINCT
	AREA.uuid,
	'area' AS type,
	AREA.title
FROM TMArea AREA
ORDER BY AREA."index"
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	areas := make([]Area, 0, 16)
	for rows.Next() {
		var area Area
		if err := rows.Scan(&area.UUID, &area.Type, &area.Title); err != nil {
			return nil, err
		}
		area.Tags, err = r.TagsOfArea(area.UUID)
		if err != nil {
			return nil, err
		}
		if includeItems {
			items, err := r.Tasks(TaskFilter{Area: area.UUID}, true)
			if err != nil {
				return nil, err
			}
			area.Items = items
		}
		areas = append(areas, area)
	}
	return areas, rows.Err()
}

func (r *Repository) Tags(includeItems bool) ([]Tag, error) {
	rows, err := r.db.Query(`
SELECT uuid, 'tag' AS type, title, shortcut
FROM TMTag
ORDER BY "index"
`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	tags := make([]Tag, 0, 16)
	for rows.Next() {
		var (
			tag      Tag
			shortcut sql.NullString
		)
		if err := rows.Scan(&tag.UUID, &tag.Type, &tag.Title, &shortcut); err != nil {
			return nil, err
		}
		tag.Shortcut = nullToString(shortcut)
		if includeItems {
			items, err := r.TaggedItems(tag.Title)
			if err != nil {
				return nil, err
			}
			tag.Items = items
		}
		tags = append(tags, tag)
	}

	return tags, rows.Err()
}

func (r *Repository) TaggedItems(tag string) ([]Task, error) {
	filter := defaultTaskFilter(TaskFilter{
		Type: "to-do",
		Tag:  tag,
	})
	return r.queryTasks(filter, true)
}

func (r *Repository) ChecklistItems(todoUUID string) ([]ChecklistItem, error) {
	createdExpr, err := r.checklistCreatedExpr()
	if err != nil {
		return nil, err
	}
	rows, err := r.db.Query(fmt.Sprintf(`
SELECT
	CHECKLIST_ITEM.title,
	CASE
		WHEN CHECKLIST_ITEM.status = 0 THEN 'incomplete'
		WHEN CHECKLIST_ITEM.status = 2 THEN 'canceled'
		WHEN CHECKLIST_ITEM.status = 3 THEN 'completed'
	END AS status,
	date(CHECKLIST_ITEM.stopDate, 'unixepoch', 'localtime') AS stop_date,
	'checklist-item' AS type,
	CHECKLIST_ITEM.uuid,
	%s AS created,
	datetime(CHECKLIST_ITEM.userModificationDate, 'unixepoch', 'localtime') AS modified
FROM TMChecklistItem CHECKLIST_ITEM
WHERE CHECKLIST_ITEM.task = ?
ORDER BY CHECKLIST_ITEM."index"
`, createdExpr), todoUUID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]ChecklistItem, 0, 8)
	for rows.Next() {
		var (
			item     ChecklistItem
			status   sql.NullString
			stopDate sql.NullString
			created  sql.NullString
			modified sql.NullString
		)
		if err := rows.Scan(
			&item.Title,
			&status,
			&stopDate,
			&item.Type,
			&item.UUID,
			&created,
			&modified,
		); err != nil {
			return nil, err
		}
		item.Status = nullToString(status)
		item.StopDate = nullToString(stopDate)
		item.Created = nullToString(created)
		item.Modified = nullToString(modified)
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r *Repository) TagsOfTask(taskUUID string) ([]string, error) {
	rows, err := r.db.Query(`
SELECT TAG.title
FROM TMTaskTag TASK_TAG
LEFT JOIN TMTag TAG ON TAG.uuid = TASK_TAG.tags
WHERE TASK_TAG.tasks = ?
ORDER BY TAG."index"
`, taskUUID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	tags := make([]string, 0, 4)
	for rows.Next() {
		var tag sql.NullString
		if err := rows.Scan(&tag); err != nil {
			return nil, err
		}
		if tag.Valid {
			tags = append(tags, tag.String)
		}
	}
	return tags, rows.Err()
}

func (r *Repository) TagsOfArea(areaUUID string) ([]string, error) {
	rows, err := r.db.Query(`
SELECT TAG.title
FROM TMAreaTag AREA_TAG
LEFT JOIN TMTag TAG ON TAG.uuid = AREA_TAG.tags
WHERE AREA_TAG.areas = ?
ORDER BY TAG."index"
`, areaUUID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	tags := make([]string, 0, 4)
	for rows.Next() {
		var tag sql.NullString
		if err := rows.Scan(&tag); err != nil {
			return nil, err
		}
		if tag.Valid {
			tags = append(tags, tag.String)
		}
	}
	return tags, rows.Err()
}

func (r *Repository) AuthToken() (string, error) {
	var token sql.NullString
	err := r.db.QueryRow(`
SELECT uriSchemeAuthenticationToken
FROM TMSettings
WHERE uuid = ?
`, authTokenRowUUID).Scan(&token)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return "", nil
		}
		return "", err
	}
	return nullToString(token), nil
}

func (r *Repository) GetByUUID(uuid string) (*Task, error) {
	tasks, err := r.queryTasks(TaskFilter{
		UUID: uuid,
	}, true)
	if err != nil {
		return nil, err
	}
	if len(tasks) == 0 {
		return nil, nil
	}
	return &tasks[0], nil
}
