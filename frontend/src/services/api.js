const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"; // "" = same address (hosted)

const TOKEN_KEY = "hr_policy_access_token";

// Reusable API request function
async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);

  const headers = {
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let body = options.body;

  if (
    body &&
    typeof body === "object" &&
    !(body instanceof FormData) &&
    !(body instanceof URLSearchParams)
  ) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    body,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";

  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null
        ? data.detail || data.message
        : data;

    const error = new Error(message || `Request failed: ${response.status}`);
    error.status = response.status; // lets the UI log out on 401
    throw error;
  }

  return data;
}

// Reads the Server-Sent Events from POST /chat/stream.
// Calls onStep(text) for every agent step, then resolves with the final answer.
async function streamChat(question, conversationId, onStep) {
  const token = localStorage.getItem(TOKEN_KEY);

  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(data.detail || `Request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop(); // keep any half-received event

    for (const raw of events) {
      const event = raw.match(/^event: (.*)$/m)?.[1];
      const dataLine = raw.match(/^data: (.*)$/m)?.[1];
      if (!event || !dataLine) continue;

      const data = JSON.parse(dataLine);
      if (event === "step") onStep?.(data.text);
      if (event === "done") result = data;
      if (event === "error") throw new Error(data.detail);
    }
  }

  if (!result) throw new Error("The answer stream ended unexpectedly");
  return result;
}

// Authentication
export const authAPI = {
  register(userData) {
    return apiRequest("/auth/register", {
      method: "POST",
      body: userData,
    });
  },

  async login(email, password) {
    const formData = new URLSearchParams();

    // FastAPI's OAuth2PasswordRequestForm expects "username".
    // Your backend uses that value to look up the email.
    formData.append("username", email);
    formData.append("password", password);

    const data = await apiRequest("/auth/login", {
      method: "POST",
      body: formData,
    });

    localStorage.setItem(TOKEN_KEY, data.access_token);

    return data;
  },

  getProfile() {
    return apiRequest("/auth/me");
  },

  updateProfile(profileData) {
    return apiRequest("/auth/me", {
      method: "PATCH",
      body: profileData,
    });
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY);
  },

  hasToken() {
    return Boolean(localStorage.getItem(TOKEN_KEY));
  },
};

// Chat and conversation history
export const chatAPI = {
  sendMessage(question, conversationId = null) {
    return apiRequest("/chat", {
      method: "POST",
      body: {
        question,
        conversation_id: conversationId,
      },
    });
  },

  // Same as sendMessage, but reports each agent step live
  streamMessage(question, conversationId = null, onStep) {
    return streamChat(question, conversationId, onStep);
  },

  getConversations() {
    return apiRequest("/chat/conversations");
  },

  getConversation(conversationId) {
    return apiRequest(`/chat/conversations/${conversationId}`);
  },

  deleteConversation(conversationId) {
    return apiRequest(`/chat/conversations/${conversationId}`, {
      method: "DELETE",
    });
  },

  // value: 1 = helpful, -1 = not helpful, 0 = remove the rating
  sendFeedback(messageId, value) {
    return apiRequest(`/chat/messages/${messageId}/feedback`, {
      method: "POST",
      body: { value },
    });
  },
};

// HR administrator: employee directory and insights
export const hrAPI = {
  getEmployees() {
    return apiRequest("/hr/employees");
  },

  updateEmployee(userId, data) {
    return apiRequest(`/hr/employees/${userId}`, {
      method: "PATCH",
      body: data,
    });
  },

  getInsights() {
    return apiRequest("/hr/insights");
  },
};

// HR Inbox: private questions to HR, and questions Humanly couldn't answer
export const requestsAPI = {
  ask(topic, question) {
    return apiRequest("/requests", { method: "POST", body: { topic, question } });
  },

  mine() {
    return apiRequest("/requests/mine");
  },

  markSeen() {
    return apiRequest("/requests/mine/seen", { method: "POST" });
  },

  inbox({ status = "", department = "" } = {}) {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (department) params.set("department", department);
    return apiRequest(`/requests?${params}`);
  },

  reply(requestId, reply, teach) {
    return apiRequest(`/requests/${requestId}/reply`, { method: "POST", body: { reply, teach } });
  },
};

// Holiday calendar
export const holidaysAPI = {
  list() {
    return apiRequest("/holidays");
  },

  add(day, name, kind) {
    return apiRequest("/holidays", { method: "POST", body: { day, name, kind } });
  },

  remove(holidayId) {
    return apiRequest(`/holidays/${holidayId}`, { method: "DELETE" });
  },
};

// Backend status
export const systemAPI = {
  health() {
    return apiRequest("/health");
  },
};

// Policy search
export const searchAPI = {
  search(query) {
    return apiRequest(`/search?q=${encodeURIComponent(query)}`);
  },
};

// HR administrator document management
export const documentsAPI = {
  getAll() {
    return apiRequest("/documents");
  },

  upload({ title, version, file }) {
    const formData = new FormData();

    formData.append("title", title);
    formData.append("version", version);
    formData.append("file", file);

    return apiRequest("/documents", {
      method: "POST",
      body: formData,
    });
  },

  replace(documentId, version, file) {
    const formData = new FormData();

    formData.append("version", version);
    formData.append("file", file);

    return apiRequest(`/documents/${documentId}`, {
      method: "PUT",
      body: formData,
    });
  },

  delete(documentId) {
    return apiRequest(`/documents/${documentId}`, {
      method: "DELETE",
    });
  },

  getChunks(documentId) {
    return apiRequest(`/documents/${documentId}/chunks`);
  },
};

export { apiRequest };