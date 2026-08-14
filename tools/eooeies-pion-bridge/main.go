package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"github.com/pion/rtcp"
	"github.com/pion/webrtc/v4"
)

const baseURL = "https://api-eu.eooeies.live"

var appEnvelope = map[string]any{
	"apiVersion": "",
	"appName":    "EOOEIES",
	"appType":    "Android",
	"bundle":     "com.mb.eooeies",
	"countlyId":  "",
	"env":        "prod-k8s",
	"tenantId":   "eooeies",
	"timeZone":   "Europe/Madrid",
	"version":    202502044,
	"versionName": "1.0.4",
}

type apiResp struct {
	Data map[string]any `json:"data"`
	Code any            `json:"code"`
	Msg  any            `json:"message"`
}

type iceItem struct {
	URLs       any    `json:"urls"`
	URL        string `json:"url"`
	Username   string `json:"username"`
	Credential string `json:"credential"`
}

type config struct {
	Email      string
	Password   string
	SN         string
	Resolution string
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func loadDotEnv(path string) {
	b, err := os.ReadFile(path)
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		kv := strings.SplitN(line, "=", 2)
		if os.Getenv(kv[0]) == "" {
			_ = os.Setenv(kv[0], kv[1])
		}
	}
}

func post(ctx context.Context, path string, body map[string]any, token string) (apiResp, error) {
	b, _ := json.Marshal(body)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+path, bytes.NewReader(b))
	if err != nil {
		return apiResp{}, err
	}
	req.Header.Set("Content-Type", "application/json; charset=UTF-8")
	req.Header.Set("User-Agent", "EOOEIES/1.0.4")
	if token != "" {
		req.Header.Set("Authorization", token)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return apiResp{}, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return apiResp{}, fmt.Errorf("api %s status %d", path, resp.StatusCode)
	}
	var ar apiResp
	if err := json.Unmarshal(raw, &ar); err != nil {
		return apiResp{}, err
	}
	return ar, nil
}

func baseBody() map[string]any {
	return map[string]any{
		"countryNo": "ES",
		"language":  "de",
		"tenantId":  "eooeies",
		"app":       appEnvelope,
	}
}

func str(v any) string {
	switch x := v.(type) {
	case float64:
		if x == float64(int64(x)) {
			return fmt.Sprintf("%d", int64(x))
		}
		return fmt.Sprintf("%f", x)
	case json.Number:
		return x.String()
	default:
		return fmt.Sprint(v)
	}
}

func login(ctx context.Context, cfg config) (string, error) {
	b := baseBody()
	b["email"] = cfg.Email
	b["password"] = cfg.Password
	b["loginType"] = 0
	ar, err := post(ctx, "/account/login/", b, "")
	if err != nil {
		return "", err
	}
	tokObj, ok := ar.Data["token"].(map[string]any)
	if !ok {
		return "", errors.New("login response missing token")
	}
	return str(tokObj["token"]), nil
}

func ticket(ctx context.Context, cfg config, token string) (map[string]any, error) {
	b := baseBody()
	b["serialNumber"] = cfg.SN
	b["liveResolution"] = cfg.Resolution
	_, _ = post(ctx, "/device/newstartlive", b, token)
	ar, err := post(ctx, "/device/getWebrtcTicket", b, token)
	if err != nil {
		return nil, err
	}
	return ar.Data, nil
}

func websocketURL(t map[string]any) string {
	signField := str(t["sign"])
	sign, rest, _ := strings.Cut(signField, "&")
	access := str(t["accessToken"])
	if vals, err := url.ParseQuery(rest); err == nil && vals.Get("accessToken") != "" {
		access = vals.Get("accessToken")
	}
	host := strings.TrimPrefix(str(t["signalServer"]), "wss://")
	host = strings.TrimPrefix(host, "ws://")
	q := url.Values{}
	q.Set("accessToken", access)
	q.Set("traceId", str(t["traceId"]))
	q.Set("time", str(t["time"]))
	q.Set("sign", sign)
	q.Set("group", str(t["groupId"]))
	q.Set("id", str(t["id"]))
	q.Set("clientType", "app")
	q.Set("status", "normal")
	q.Set("role", str(t["role"]))
	q.Set("name", str(t["id"]))
	return "wss://" + host + ":443/v1/viewer/" + sign + "?" + q.Encode()
}

func iceServers(t map[string]any) []webrtc.ICEServer {
	b, _ := json.Marshal(t["iceServer"])
	var items []iceItem
	_ = json.Unmarshal(b, &items)
	out := []webrtc.ICEServer{}
	for _, it := range items {
		urls := []string{}
		switch u := it.URLs.(type) {
		case []any:
			for _, x := range u {
				urls = append(urls, fmt.Sprint(x))
			}
		case string:
			urls = append(urls, u)
		}
		if it.URL != "" {
			urls = append(urls, it.URL)
		}
		if len(urls) > 0 {
			out = append(out, webrtc.ICEServer{URLs: urls, Username: it.Username, Credential: it.Credential})
		}
	}
	return out
}

func b64(v any) string {
	b, _ := json.Marshal(v)
	return base64.StdEncoding.EncodeToString(b)
}

func sendJSON(c *websocket.Conn, v any) error {
	b, _ := json.Marshal(v)
	return c.WriteMessage(websocket.TextMessage, b)
}

type h264Depay struct {
	cur []byte
	w   io.Writer
}

func (d *h264Depay) emit(nal []byte) {
	if len(nal) == 0 {
		return
	}
	_, _ = d.w.Write([]byte{0, 0, 0, 1})
	_, _ = d.w.Write(nal)
}

func (d *h264Depay) push(payload []byte) {
	if len(payload) == 0 {
		return
	}
	t := payload[0] & 31
	if t >= 1 && t <= 23 {
		if len(d.cur) > 0 {
			d.emit(d.cur)
			d.cur = nil
		}
		d.emit(payload)
		return
	}
	if t == 28 && len(payload) >= 2 {
		fuInd, fuHdr := payload[0], payload[1]
		start := fuHdr&0x80 != 0
		end := fuHdr&0x40 != 0
		nalType := fuHdr & 31
		if start {
			if len(d.cur) > 0 {
				d.emit(d.cur)
			}
			nalHeader := (fuInd & 0xE0) | nalType
			d.cur = append([]byte{nalHeader}, payload[2:]...)
		} else if len(d.cur) > 0 {
			d.cur = append(d.cur, payload[2:]...)
		}
		if end && len(d.cur) > 0 {
			d.emit(d.cur)
			d.cur = nil
		}
	}
}

func makeAPI() *webrtc.API {
	se := webrtc.SettingEngine{}
	se.SetNetworkTypes([]webrtc.NetworkType{webrtc.NetworkTypeUDP4})
	m := &webrtc.MediaEngine{}
	_ = m.RegisterCodec(webrtc.RTPCodecParameters{RTPCodecCapability: webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypePCMU, ClockRate: 8000, RTCPFeedback: []webrtc.RTCPFeedback{{Type: "nack"}}}, PayloadType: 0}, webrtc.RTPCodecTypeAudio)
	_ = m.RegisterCodec(webrtc.RTPCodecParameters{RTPCodecCapability: webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypeH264, ClockRate: 90000, SDPFmtpLine: "level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f", RTCPFeedback: []webrtc.RTCPFeedback{{Type: "nack"}, {Type: "nack", Parameter: "pli"}, {Type: "ccm", Parameter: "fir"}, {Type: "goog-remb"}}}, PayloadType: 101}, webrtc.RTPCodecTypeVideo)
	return webrtc.NewAPI(webrtc.WithMediaEngine(m), webrtc.WithSettingEngine(se))
}

func run(ctx context.Context, cfg config) error {
	token, err := login(ctx, cfg)
	if err != nil {
		return err
	}
	t, err := ticket(ctx, cfg, token)
	if err != nil {
		return err
	}
	api := makeAPI()
	pc, err := api.NewPeerConnection(webrtc.Configuration{ICEServers: iceServers(t), BundlePolicy: webrtc.BundlePolicyMaxBundle})
	if err != nil {
		return err
	}
	defer pc.Close()
	pc.OnICEConnectionStateChange(func(s webrtc.ICEConnectionState) { fmt.Fprintln(os.Stderr, "ICE", s.String()) })
	pc.OnConnectionStateChange(func(s webrtc.PeerConnectionState) { fmt.Fprintln(os.Stderr, "PC", s.String()) })

	dc, err := pc.CreateDataChannel("vicoo", nil)
	if err != nil {
		return err
	}
	dc.OnOpen(func() {
		fmt.Fprintln(os.Stderr, "DC_OPEN")
		ts := time.Now().Unix()
		msgs := []map[string]any{
			{"requestID": fmt.Sprintf("cmd_%d", ts), "connectionID": "7893feb", "timeStamp": ts, "action": "getStatus", "targetId": cfg.SN},
			{"requestID": fmt.Sprintf("cmd_%d", ts+1), "connectionID": "7893feb", "timeStamp": ts, "action": "startLive", "targetId": cfg.SN, "size": cfg.Resolution, "resolution": cfg.Resolution},
		}
		for _, m := range msgs {
			b, _ := json.Marshal(m)
			fmt.Fprintln(os.Stderr, "DC_SEND", string(b))
			_ = dc.SendText(string(b))
		}
	})
	dc.OnMessage(func(msg webrtc.DataChannelMessage) { fmt.Fprintln(os.Stderr, "DC_MSG", string(msg.Data)) })

	_, _ = pc.AddTransceiverFromKind(webrtc.RTPCodecTypeAudio, webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly})
	_, _ = pc.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo, webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly})

	pc.OnTrack(func(track *webrtc.TrackRemote, recv *webrtc.RTPReceiver) {
		fmt.Fprintln(os.Stderr, "TRACK", track.Kind().String(), track.Codec().MimeType)
		if track.Kind() == webrtc.RTPCodecTypeVideo {
			go func() {
				for i := 0; i < 20; i++ {
					time.Sleep(time.Second)
					_ = pc.WriteRTCP([]rtcp.Packet{&rtcp.PictureLossIndication{MediaSSRC: uint32(track.SSRC())}, &rtcp.FullIntraRequest{SenderSSRC: 1, MediaSSRC: uint32(track.SSRC()), FIR: []rtcp.FIREntry{{SSRC: uint32(track.SSRC()), SequenceNumber: uint8(i + 1)}}}})
				}
			}()
			go func() {
				depay := &h264Depay{w: os.Stdout}
				for {
					pkt, _, err := track.ReadRTP()
					if err != nil {
						fmt.Fprintln(os.Stderr, "VIDEO_END", err)
						return
					}
					depay.push(pkt.Payload)
				}
			}()
		} else {
			go func() {
				for {
					if _, _, err := track.ReadRTP(); err != nil {
						return
					}
				}
			}()
		}
	})

	dialer := websocket.Dialer{TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}}
	ws, _, err := dialer.Dial(websocketURL(t), http.Header{"User-Agent": []string{"EOOEIES/1.0.4"}})
	if err != nil {
		return err
	}
	defer ws.Close()
	fmt.Fprintln(os.Stderr, "WS_OPEN")
	_ = sendJSON(ws, map[string]any{"method": "JOIN_LIVE", "group": str(t["groupId"]), "role": str(t["role"]), "name": str(t["id"]), "traceId": str(t["traceId"]), "recipientClientId": str(t["groupId"])})

	peerIn := false
	answerSet := false
	deadline := time.Now().Add(time.Duration(atoi(getenv("EOOEIES_RUNTIME_SECONDS", "120"))) * time.Second)
	for time.Now().Before(deadline) {
		_ = ws.SetReadDeadline(time.Now().Add(15 * time.Second))
		_, data, err := ws.ReadMessage()
		if err != nil {
			fmt.Fprintln(os.Stderr, "WS_END", err)
			break
		}
		var obj map[string]any
		_ = json.Unmarshal(data, &obj)
		mt := str(obj["messageType"])
		if mt != "<nil>" {
			fmt.Fprintln(os.Stderr, "SIG", mt)
		}
		if mt == "PEER_IN" && !peerIn {
			peerIn = true
			offer, err := pc.CreateOffer(nil)
			if err != nil {
				return err
			}
			if err = pc.SetLocalDescription(offer); err != nil {
				return err
			}
			<-webrtc.GatheringCompletePromise(pc)
			sdp := pc.LocalDescription().SDP
			msg := map[string]any{"method": "TRANSMIT", "messageType": "SDP_OFFER", "messagePayload": b64(map[string]string{"type": "offer", "sdp": sdp}), "mode": "vicoo", "recipientClientId": str(t["groupId"]), "senderClientId": str(t["id"]), "sessionId": fmt.Sprintf("Android-%s-%d", cfg.SN, time.Now().UnixMilli()), "viewerType": "a4x_sdk", "resolution": cfg.Resolution, "version": "0.0.1"}
			_ = sendJSON(ws, msg)
			fmt.Fprintln(os.Stderr, "OFFER_SENT")
		}
		if mp, ok := obj["messagePayload"].(string); ok && mp != "" && !answerSet {
			dec, err := base64.StdEncoding.DecodeString(mp)
			if err == nil {
				var p map[string]any
				if json.Unmarshal(dec, &p) == nil && p["type"] == "answer" {
					err = pc.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: str(p["sdp"])})
					if err != nil {
						return err
					}
					answerSet = true
					fmt.Fprintln(os.Stderr, "ANSWER_SET")
				}
			}
		}
	}
	return nil
}

func atoi(s string) int {
	var n int
	_, _ = fmt.Sscanf(s, "%d", &n)
	if n <= 0 {
		return 120
	}
	return n
}

func main() {
	loadDotEnv(getenv("EOOEIES_ENV_FILE", "/config/eooeies/.env"))
	loadDotEnv(".env")
	cfg := config{Email: os.Getenv("EOOEIES_EMAIL"), Password: os.Getenv("EOOEIES_PASSWORD"), SN: os.Getenv("EOOEIES_SN"), Resolution: getenv("EOOEIES_RESOLUTION", "1280x720")}
	if cfg.Email == "" || cfg.Password == "" || cfg.SN == "" {
		fmt.Fprintln(os.Stderr, "missing EOOEIES_EMAIL, EOOEIES_PASSWORD or EOOEIES_SN")
		os.Exit(2)
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(atoi(getenv("EOOEIES_RUNTIME_SECONDS", "120"))+30)*time.Second)
	defer cancel()
	if err := run(ctx, cfg); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
