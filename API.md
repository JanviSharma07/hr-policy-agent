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
| POST | `/auth/register` | JSON `{email, password, join_date?, department?, job_title?, city?}` (`join_date` as `YYYY-MM-DD`) | the user |
| POST | `/auth/login` | **form data** (not JSON): `username` (the email), `password` | `{access_token, token_type, role}` |
| GET | `/auth/me` | – | `{id, email, role, join_date, department, job_title, skills, city}` (+ `grade` for HR admins only) |
| PATCH | `/auth/me` | JSON with any of `{job_title, city, skills}` | the updated user |
| GET | `/auth/departments` | – | list of department names |

The grade is never shown to employees and they can't change it: it decides travel entitlements, so only HR sets it (see `/hr/employees`). Department and joining date are also managed by HR after sign-up.

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


## Answer feedback

| Method | Route | Body | Returns |
|---|---|---|---|
| POST | `/chat/messages/{message_id}/feedback` | JSON `{value}`: `1` helpful, `-1` not helpful, `0` remove | `{message_id, feedback}` |

`message_id` comes from the `done` event of `/chat/stream` (and from `/chat`). Messages in `GET /chat/conversations/{id}` now include `id` and `feedback`.

## HR admin: employees and insights (403 for employees)

| Method | Route | Body | Returns |
|---|---|---|---|
| GET | `/hr/employees` | – | every user with `grade` and `questions_asked` |
| PATCH | `/hr/employees/{user_id}` | JSON with any of `{department, job_title, grade, city, join_date, skills}` | the updated user |
| GET | `/hr/insights` | – | `{totals, by_intent, by_department, unanswered, not_helpful}` |

`unanswered` lists questions that got the "This isn't covered" reply: these are gaps in the policies.


## HR Inbox (private questions and questions Humanly couldn't answer)

| Method | Route | Who | Body | Returns |
|---|---|---|---|---|
| POST | `/requests` | employee | JSON `{topic, question}` | the request (`kind: "private"`) |
| GET | `/requests/mine` | employee | – | `{items, unseen}` (unseen = HR replies not read yet) |
| POST | `/requests/mine/seen` | employee | – | marks replies as read |
| GET | `/requests?status=&department=` | HR | – | requests with the employee's details |
| POST | `/requests/{id}/reply` | HR | JSON `{reply, teach}` | the answered request |

When Humanly answers "This isn't covered", a request with `kind: "unanswered"` is created automatically.
`teach: true` adds the reply to ChromaDB under the document "HR Answers", so the AI can answer that question itself next time. Private requests can never be taught and never reach the AI.

## Holidays

| Method | Route | Who | Body | Returns |
|---|---|---|---|---|
| GET | `/holidays` | anyone signed in | – | `[{id, day, name, kind}]` (`kind`: `fixed` or `optional`) |
| POST | `/holidays` | HR | JSON `{day, name, kind}` | the new holiday |
| DELETE | `/holidays/{id}` | HR | – | `{deleted}` |

The 2026 list is added on first start and matches section 6 of Holiday Policy 2026.2 (`policy_updates/`).
