INSERT INTO TMArea (uuid, title, "index") VALUES
  ('area-work', 'Work', 1),
  ('area-personal', 'Personal', 2);

INSERT INTO TMTag (uuid, title, shortcut, "index") VALUES
  ('tag-work', 'work', 'cmd+1', 1),
  ('tag-home', 'home', 'cmd+2', 2);

INSERT INTO TMAreaTag (areas, tags) VALUES
  ('area-work', 'tag-work');

INSERT INTO TMSettings (uuid, uriSchemeAuthenticationToken) VALUES
  ('RhAzEf6qDxCD5PmnZVtBZR', 'test-auth-token');

INSERT INTO TMTask (
  uuid, type, trashed, title, status, area, project, heading, notes, start, startDate,
  deadline, reminderTime, stopDate, creationDate, userModificationDate, "index", todayIndex, deadlineSuppressionDate, rt1_recurrenceRule
) VALUES
  ('project-active', 1, 0, 'Active Project', 0, 'area-work', NULL, NULL, 'Project notes', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-10 day'), strftime('%s','now','-2 day'), 1, 0, NULL, NULL),
  ('project-someday', 1, 0, 'Someday Project', 0, 'area-personal', NULL, NULL, 'Someday project notes', 2, NULL, NULL, NULL, NULL, strftime('%s','now','-20 day'), strftime('%s','now','-3 day'), 2, 0, NULL, NULL),
  ('heading-active', 2, 0, 'Phase Active', 0, NULL, 'project-active', NULL, '', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-8 day'), strftime('%s','now','-2 day'), 3, 0, NULL, NULL),
  ('heading-someday', 2, 0, 'Phase Someday', 0, NULL, 'project-someday', NULL, '', 2, NULL, NULL, NULL, NULL, strftime('%s','now','-18 day'), strftime('%s','now','-4 day'), 4, 0, NULL, NULL),
  ('todo-inbox', 0, 0, 'Inbox Task', 0, NULL, NULL, NULL, 'Inbox notes', 0, NULL, NULL, NULL, NULL, strftime('%s','now','-4 day'), strftime('%s','now','-1 day'), 10, 0, NULL, NULL),
  ('todo-checklist', 0, 0, 'Checklist Task', 0, NULL, NULL, NULL, 'Checklist notes', 0, NULL, NULL, NULL, NULL, strftime('%s','now','-3 day'), strftime('%s','now','-1 day'), 11, 0, NULL, NULL),
  ('todo-anytime-active', 0, 0, 'Anytime Active Task', 0, NULL, 'project-active', NULL, '', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-6 day'), strftime('%s','now','-1 day'), 12, 0, NULL, NULL),
  ('todo-anytime-someday-project', 0, 0, 'Anytime Someday Project Task', 0, NULL, 'project-someday', NULL, '', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-5 day'), strftime('%s','now','-1 day'), 13, 0, NULL, NULL),
  ('todo-heading-someday', 0, 0, 'Heading Someday Task', 0, NULL, NULL, 'heading-someday', '', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-5 day'), strftime('%s','now','-1 day'), 14, 0, NULL, NULL),
  ('todo-someday-standalone', 0, 0, 'Standalone Someday Task', 0, NULL, NULL, NULL, '', 2, NULL, NULL, NULL, NULL, strftime('%s','now','-9 day'), strftime('%s','now','-1 day'), 15, 0, NULL, NULL),
  ('todo-upcoming', 0, 0, 'Upcoming Task', 0, NULL, NULL, NULL, '', 2,
    ((strftime('%Y', date('now','+3 day','localtime')) << 16) | (strftime('%m', date('now','+3 day','localtime')) << 12) | (strftime('%d', date('now','+3 day','localtime')) << 7)),
    NULL, NULL, NULL, strftime('%s','now','-2 day'), strftime('%s','now','-1 day'), 16, 0, NULL, NULL),
  ('todo-today-regular', 0, 0, 'Today Regular Task', 0, NULL, NULL, NULL, '', 1,
    ((strftime('%Y', date('now','localtime')) << 16) | (strftime('%m', date('now','localtime')) << 12) | (strftime('%d', date('now','localtime')) << 7)),
    NULL, NULL, NULL, strftime('%s','now','-2 day'), strftime('%s','now','-1 day'), 17, 1, NULL, NULL),
  ('todo-unconfirmed-scheduled', 0, 0, 'Today Predicted Someday Task', 0, NULL, NULL, NULL, '', 2,
    ((strftime('%Y', date('now','-1 day','localtime')) << 16) | (strftime('%m', date('now','-1 day','localtime')) << 12) | (strftime('%d', date('now','-1 day','localtime')) << 7)),
    NULL, NULL, NULL, strftime('%s','now','-2 day'), strftime('%s','now','-1 day'), 18, 2, NULL, NULL),
  ('todo-overdue', 0, 0, 'Today Overdue Task', 0, NULL, NULL, NULL, '', 1, NULL,
    ((strftime('%Y', date('now','-1 day','localtime')) << 16) | (strftime('%m', date('now','-1 day','localtime')) << 12) | (strftime('%d', date('now','-1 day','localtime')) << 7)),
    NULL, NULL, strftime('%s','now','-3 day'), strftime('%s','now','-1 day'), 19, 3, NULL, NULL),
  ('todo-completed', 0, 0, 'Completed Task', 3, NULL, NULL, NULL, '', 1, NULL, NULL, NULL, strftime('%s','now','-1 day'), strftime('%s','now','-8 day'), strftime('%s','now','-1 day'), 20, 0, NULL, NULL),
  ('todo-canceled', 0, 0, 'Canceled Task', 2, NULL, NULL, NULL, '', 1, NULL, NULL, NULL, strftime('%s','now','-2 day'), strftime('%s','now','-7 day'), strftime('%s','now','-2 day'), 21, 0, NULL, NULL),
  ('todo-trash', 0, 1, 'Trash Task', 0, NULL, NULL, NULL, '', 1, NULL, NULL, NULL, NULL, strftime('%s','now','-6 day'), strftime('%s','now','-2 day'), 22, 0, NULL, NULL);

INSERT INTO TMTaskTag (tasks, tags) VALUES
  ('todo-inbox', 'tag-home'),
  ('todo-anytime-active', 'tag-work');

INSERT INTO TMChecklistItem (uuid, task, title, status, stopDate, userModificationDate, "index") VALUES
  ('check-1', 'todo-checklist', 'First item', 3, strftime('%s','now','-1 day'), strftime('%s','now','-1 day'), 1),
  ('check-2', 'todo-checklist', 'Second item', 0, NULL, strftime('%s','now','-1 day'), 2);

