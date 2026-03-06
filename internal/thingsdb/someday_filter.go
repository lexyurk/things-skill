package thingsdb

func (r *Repository) GetSomedayContext() (map[string]struct{}, map[string]string, error) {
	somedayProjects, err := r.queryTasks(defaultTaskFilter(TaskFilter{
		Type:  "project",
		Start: "Someday",
	}), false)
	if err != nil {
		return nil, nil, err
	}

	projectIDs := make(map[string]struct{}, len(somedayProjects))
	for _, project := range somedayProjects {
		projectIDs[project.UUID] = struct{}{}
	}
	if len(projectIDs) == 0 {
		return projectIDs, map[string]string{}, nil
	}

	headingToProject := make(map[string]string, 32)
	for projectID := range projectIDs {
		headings, err := r.queryTasks(defaultTaskFilter(TaskFilter{
			Type:    "heading",
			Project: projectID,
		}), false)
		if err != nil {
			return nil, nil, err
		}
		for _, heading := range headings {
			headingToProject[heading.UUID] = projectID
		}
	}

	return projectIDs, headingToProject, nil
}

func (r *Repository) IsInSomedayProject(task Task, projectIDs map[string]struct{}, headingToProject map[string]string) bool {
	if task.ProjectUUID != "" {
		_, ok := projectIDs[task.ProjectUUID]
		return ok
	}
	if task.HeadingUUID != "" {
		_, ok := headingToProject[task.HeadingUUID]
		return ok
	}
	return false
}

func (r *Repository) FilterSomedayProjectTasks(tasks []Task) ([]Task, error) {
	projectIDs, headingToProject, err := r.GetSomedayContext()
	if err != nil {
		return nil, err
	}
	if len(projectIDs) == 0 {
		return tasks, nil
	}

	filtered := make([]Task, 0, len(tasks))
	for _, task := range tasks {
		if r.IsInSomedayProject(task, projectIDs, headingToProject) {
			continue
		}
		filtered = append(filtered, task)
	}
	return filtered, nil
}
