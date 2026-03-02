package thingsdb

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestAreaTagsJSONTag(t *testing.T) {
	area := Area{
		UUID:  "area-1",
		Type:  "area",
		Title: "Area",
		Tags:  []string{"work"},
	}
	encoded, err := json.Marshal(area)
	if err != nil {
		t.Fatal(err)
	}
	text := string(encoded)
	if !strings.Contains(text, `"tags":["work"]`) {
		t.Fatalf("expected lowercase tags key in JSON, got %s", text)
	}
	if strings.Contains(text, `"Tags"`) {
		t.Fatalf("did not expect uppercase Tags key in JSON, got %s", text)
	}
}
