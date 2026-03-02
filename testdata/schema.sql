CREATE TABLE TMTask (
  uuid TEXT PRIMARY KEY,
  type INTEGER NOT NULL,
  trashed INTEGER NOT NULL DEFAULT 0,
  title TEXT NOT NULL,
  status INTEGER NOT NULL DEFAULT 0,
  area TEXT,
  project TEXT,
  heading TEXT,
  notes TEXT,
  start INTEGER NOT NULL DEFAULT 1,
  startDate INTEGER,
  deadline INTEGER,
  reminderTime INTEGER,
  stopDate REAL,
  creationDate REAL,
  userModificationDate REAL,
  "index" INTEGER NOT NULL DEFAULT 0,
  todayIndex INTEGER NOT NULL DEFAULT 0,
  deadlineSuppressionDate REAL,
  rt1_recurrenceRule TEXT
);

CREATE TABLE TMArea (
  uuid TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  "index" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE TMTag (
  uuid TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  shortcut TEXT,
  "index" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE TMTaskTag (
  tasks TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE TMAreaTag (
  areas TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE TMChecklistItem (
  uuid TEXT PRIMARY KEY,
  task TEXT NOT NULL,
  title TEXT NOT NULL,
  status INTEGER NOT NULL DEFAULT 0,
  stopDate REAL,
  userModificationDate REAL,
  "index" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE TMSettings (
  uuid TEXT PRIMARY KEY,
  uriSchemeAuthenticationToken TEXT
);

