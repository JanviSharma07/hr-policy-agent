# HR Policy Agent – API guide for the frontend

Backend runs at `http://127.0.0.1:8000`. Every route is listed and testable at `http://127.0.0.1:8000/docs`.
CORS allows `http://localhost:5173` (Vite). Tell the backend team if your dev server uses another port.

## Auth

Every request except register and login needs this header:

```
Authorization: Bearer <access_token>
```

| Method | Route | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | JSON `{email, password, join_date?, grade?, city?}` (`join_date` as `YYYY-MM-DD`) | the user |
| POST | `/auth/login` | **form data** (not JSON): `username` (the email), `password` | `{access_token, token_type, role}` |
| GET | `/auth/me` | – | `{id, email, role, join_date, grade, city}` |
| PATCH | `/auth/me` | JSON with any of `{join_date, grade, city}` | the updated user |

`role` is `employee` or `hr_admin`. Show the HR documents page only to `hr_admin` (the API blocks employees anyway, with 403).

Login example:

```js
const res = await fetch("http://127.0.0.1:8000/auth/login", {
  method: "POST",
  body: new URLSearchParams({ username: email, password }),
});
const { access_token, role } = await res.json();
```

## Chat

### POST `/chat`

Body: `{ "question": "...", "conversation_id": 12 }` – leave out `conversation_id` to start a new chat.

```json
{
  "conversation_id": 12,
  "intent": "calculation",
  "answer": "- Four-wheeler mileage: Rs. 4,800\n\nTolls and parking are paid at actuals.",
  "citations": [
    { "document_id": 2, "title": "Travel Policy", "version": "2026", "status": "current",
      "section": "4. Own Vehicle Mileage", "page": null, "text": "full source paragraph" }
  ],
  "trace": ["Router (Gemini placeholder): calculation", "Searched policies: 1 relevant section(s) found", "..."]
}
```

- `answer` contains `\n` line breaks and `- ` bullets: render with `white-space: pre-wrap` (or a markdown renderer).
- `citations`: show each as a chip like **Travel Policy · v2026 · 4. Own Vehicle Mileage · p.3**. `page` is `null` for Word files, so hide it then. Clicking a chip can show `text`.
- `status` is `archived` only in answers comparing old and new versions.
- `trace`: the agent's steps, nice to show in a collapsible "How I got this" panel.
- `intent` is one of `policy_qa`, `summarize`, `compare`, `eligibility`, `calculation`, `out_of_scope`.
- Sometimes the answer is a **question back to the user** (e.g. "How many km was the trip?"). The user just replies in the same chat, with the same `conversation_id`.

### POST `/chat/stream` – live agent steps

Same body as `/chat`, but the reply arrives as Server-Sent Events, so the UI can show each step as it happens:

```
event: step
data: {"text": "Router (Gemini placeholder): calculation"}

event: done
data: { ...same object as POST /chat returns... }
```

On failure it sends `event: error` with `{"detail": "..."}`.
`EventSource` can't send POST or headers, so read it with `fetch`:

```js
const res = await fetch("http://127.0.0.1:8000/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ question, conversation_id }),
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const events = buffer.split("\n\n");
  buffer = events.pop();                       // keep any half-received event
  for (const raw of events) {
    const event = raw.match(/^event: (.*)$/m)?.[1];
    const data = JSON.parse(raw.match(/^data: (.*)$/m)?.[1] ?? "{}");
    if (event === "step") showStep(data.text);
    if (event === "done") showAnswer(data);    // same shape as POST /chat
    if (event === "error") showError(data.detail);
  }
}
```

### Chat history (sidebar)

| Method | Route | Returns |
|---|---|---|
| GET | `/chat/conversations` | `[{id, title, created_at}]`, newest first |
| GET | `/chat/conversations/{id}` | `{id, title, messages: [{sender, content, citations, created_at}]}` |
| DELETE | `/chat/conversations/{id}` | `{deleted}` |

`sender` is `user` or `assistant`.

## HR documents (hr_admin only)

| Method | Route | Body | Notes |
|---|---|---|---|
| GET | `/documents` | – | `[{id, family_id, title, version, status, chunk_count, uploaded_at}]` |
| POST | `/documents` | **multipart form**: `title`, `version`, `file` (PDF or DOCX) | upload a new policy |
| PUT | `/documents/{id}` | **multipart form**: `version`, `file` | upload a new version; the old one becomes `archived` |
| DELETE | `/documents/{id}` | – | deletes the policy **and all its versions** |
| GET | `/documents/{id}/chunks` | – | how the file was split (for checking) |

- Group the list by `family_id`: one row per policy, with older versions (`status: "archived"`) shown underneath.
- Only `current` versions have a Replace button (the API rejects replacing an archived one).
- First upload takes about a minute (models load); show a spinner.

Upload example:

```js
const form = new FormData();
form.append("title", "Leave Policy");
form.append("version", "2026");
form.append("file", fileInput.files[0]);
await fetch("http://127.0.0.1:8000/documents", {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },   // don't set Content-Type yourself
  body: form,
});
```

## Errors

Errors come back as `{"detail": "message"}`: 400 bad input, 401 not logged in or token expired (send to login), 403 not HR admin, 404 not found, 502 the AI service failed (show "Try again").

## Test accounts

- Employee: `emp@company.com` / `Emp123`
- HR admin: `hr@company.com` / `Admin123`
