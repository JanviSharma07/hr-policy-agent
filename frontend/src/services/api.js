const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

    throw new Error(message || `Request failed: ${response.status}`);
  }

  return data;
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