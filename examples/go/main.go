// Parse a public share link with Fastdown and save the best media entry.
//
//	export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
//	go run ./examples/go "https://v.douyin.com/xxxx/"
//
// Standard library only.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

const (
	defaultAPI = "https://fastdown.pro/api"
	userAgent  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

type parseRequest struct {
	URL    string         `json:"url"`
	Prefer map[string]any `json:"prefer"`
}

type mediaItem struct {
	Type      string `json:"type"`
	URL       string `json:"url"`
	Watermark bool   `json:"watermark"`
	Quality   string `json:"quality"`
	Ext       string `json:"ext"`
}

type quotaInfo struct {
	PlanID     string `json:"plan_id"`
	DailyLimit int    `json:"daily_limit"`
	Used       int    `json:"used"`
	Remaining  int    `json:"remaining"`
	ResetAt    string `json:"reset_at"`
}

type parseData struct {
	Platform string      `json:"platform"`
	Title    string      `json:"title"`
	Author   string      `json:"author"`
	Media    []mediaItem `json:"media"`
	Warnings []string    `json:"warnings"`
	Quota    quotaInfo   `json:"quota"`
}

type apiError struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Retryable bool   `json:"retryable"`
}

type envelope struct {
	OK        bool      `json:"ok"`
	RequestID string    `json:"request_id"`
	Data      parseData `json:"data"`
	Error     *apiError `json:"error"`
}

func main() {
	apiDefault := defaultAPI
	if v := os.Getenv("FASTDOWN_API_BASE"); v != "" {
		apiDefault = v
	}

	outDir := flag.String("o", "./downloads", "output directory")
	mediaType := flag.String("type", "", "preferred media type: video, audio, image")
	apiBase := flag.String("api", apiDefault, "API base URL (also read from FASTDOWN_API_BASE)")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Fprintln(os.Stderr, "usage: go run . [flags] <share url or share text>")
		flag.PrintDefaults()
		os.Exit(2)
	}

	key := os.Getenv("FASTDOWN_API_KEY")
	if key == "" {
		fmt.Fprintln(os.Stderr, "set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)")
		os.Exit(5)
	}

	client := &http.Client{Timeout: 60 * time.Second}
	env, status, err := parse(client, *apiBase, key, flag.Arg(0), *mediaType)
	if err != nil {
		fmt.Fprintf(os.Stderr, "parse failed: %v\n", err)
		os.Exit(1)
	}
	if !env.OK {
		code, msg, retryable := "UNKNOWN", "request failed", false
		if env.Error != nil {
			code, msg, retryable = env.Error.Code, env.Error.Message, env.Error.Retryable
		}
		fmt.Fprintf(os.Stderr, "parse failed: %s — %s\n", code, msg)
		fmt.Fprintf(os.Stderr, "request_id: %s  retryable: %t\n", env.RequestID, retryable)
		if status == http.StatusUnauthorized || status == http.StatusForbidden || status == http.StatusTooManyRequests {
			os.Exit(5)
		}
		os.Exit(3)
	}

	data := env.Data
	if len(data.Media) == 0 || data.Media[0].URL == "" {
		fmt.Fprintln(os.Stderr, "no downloadable media in the response")
		os.Exit(3)
	}

	item := data.Media[0]
	ext := item.Ext
	if ext == "" {
		ext = "mp4"
	}
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "create output dir: %v\n", err)
		os.Exit(1)
	}
	dest := filepath.Join(*outDir, safeName(data.Title)+"."+ext)

	fmt.Printf("downloading: %s (%s)\n", data.Title, data.Platform)
	written, err := download(client, item.URL, dest)
	if err != nil {
		fmt.Fprintf(os.Stderr, "download failed: %v\n", err)
		os.Exit(1)
	}

	for _, w := range data.Warnings {
		fmt.Fprintf(os.Stderr, "warning: %s\n", w)
	}
	fmt.Printf("saved: %s (%d bytes)\n", dest, written)
	fmt.Printf("quota: %d/%d remaining\n", data.Quota.Remaining, data.Quota.DailyLimit)
}

func parse(client *http.Client, api, key, input, mediaType string) (envelope, int, error) {
	prefer := map[string]any{"watermark": false}
	if mediaType != "" {
		prefer["media_type"] = mediaType
	}
	payload, err := json.Marshal(parseRequest{URL: input, Prefer: prefer})
	if err != nil {
		return envelope{}, 0, err
	}

	req, err := http.NewRequest(http.MethodPost, strings.TrimRight(api, "/")+"/v1/parse", bytes.NewReader(payload))
	if err != nil {
		return envelope{}, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return envelope{}, 0, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return envelope{}, resp.StatusCode, err
	}

	var env envelope
	if err := json.Unmarshal(body, &env); err != nil {
		return envelope{}, resp.StatusCode, fmt.Errorf("HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	return env, resp.StatusCode, nil
}

func download(client *http.Client, url, dest string) (int64, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("User-Agent", userAgent)

	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	file, err := os.Create(dest)
	if err != nil {
		return 0, err
	}
	defer file.Close()

	return io.Copy(file, resp.Body)
}

var unsafeName = regexp.MustCompile(`[\\/:*?"<>|\x00-\x1f]`)

func safeName(title string) string {
	name := unsafeName.ReplaceAllString(title, "")
	name = strings.Join(strings.Fields(name), " ")
	if len([]rune(name)) > 80 {
		name = string([]rune(name)[:80])
	}
	if name == "" {
		return "fastdown-media"
	}
	return name
}
