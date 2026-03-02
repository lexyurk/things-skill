package thingsdb

import (
	"fmt"
	"sort"
	"strings"
)

const (
	ViewInbox    = "inbox"
	ViewToday    = "today"
	ViewUpcoming = "upcoming"
	ViewAnytime  = "anytime"
	ViewSomeday  = "someday"
	ViewLogbook  = "logbook"
	ViewTrash    = "trash"
)

func (r *Repository) ListView(view string, logbookPeriod string, logbookLimit int) ([]Task, error) {
	switch strings.ToLower(view) {
	case ViewInbox:
		return r.Inbox()
	case ViewToday:
		return r.Today()
	case ViewUpcoming:
		return r.Upcoming()
	case ViewAnytime:
		return r.Anytime()
	case ViewSomeday:
		return r.Someday()
	case ViewLogbook:
		if logbookPeriod != "" {
			completed, err := r.Tasks(TaskFilter{
				Status:         "completed",
				Last:           logbookPeriod,
				Trashed:        boolPtr(false),
				ContextTrashed: boolPtr(false),
			}, true)
			if err != nil {
				return nil, err
			}
			canceled, err := r.Tasks(TaskFilter{
				Status:         "canceled",
				Last:           logbookPeriod,
				Trashed:        boolPtr(false),
				ContextTrashed: boolPtr(false),
			}, true)
			if err != nil {
				return nil, err
			}
			tasks := append(completed, canceled...)
			sort.SliceStable(tasks, func(i, j int) bool {
				return tasks[i].StopDate > tasks[j].StopDate
			})
			if logbookLimit > 0 && len(tasks) > logbookLimit {
				tasks = tasks[:logbookLimit]
			}
			return tasks, nil
		}
		tasks, err := r.Logbook()
		if err != nil {
			return nil, err
		}
		if logbookLimit > 0 && len(tasks) > logbookLimit {
			tasks = tasks[:logbookLimit]
		}
		return tasks, nil
	case ViewTrash:
		return r.Trash()
	default:
		return nil, fmt.Errorf("unknown view %q", view)
	}
}
