// Authentication utilities and session management

export interface User {
    username: string;
    displayName: string;
}

// Hardcoded users for local authentication
const USERS = [
    { username: "admin", password: "admin123", displayName: "Admin User" },
    { username: "tao", password: "tao123", displayName: "TAO Team Member" },
    { username: "demo", password: "demo", displayName: "Demo User" },
];

// Session expiry time in milliseconds (15 minutes)
const SESSION_EXPIRY_MS = 15 * 60 * 1000;

const SESSION_KEY = "tao_lens_session";
const SESSION_EXPIRY_KEY = "tao_lens_session_expiry";
const SESSION_LOGIN_TIME_KEY = "tao_lens_login_time";

export function isAdmin(user: User | null): boolean {
    return user?.username === "admin";
}

export function authenticate(username: string, password: string): User | null {
    const user = USERS.find(
        (u) => u.username === username && u.password === password
    );

    if (user) {
        const sessionUser: User = {
            username: user.username,
            displayName: user.displayName,
        };

        // Store session
        const now = Date.now();
        const expiryTime = now + SESSION_EXPIRY_MS;
        localStorage.setItem(SESSION_KEY, JSON.stringify(sessionUser));
        localStorage.setItem(SESSION_EXPIRY_KEY, expiryTime.toString());
        localStorage.setItem(SESSION_LOGIN_TIME_KEY, now.toString());

        return sessionUser;
    }

    return null;
}

export function getSession(): User | null {
    try {
        const sessionData = localStorage.getItem(SESSION_KEY);
        const expiryTime = localStorage.getItem(SESSION_EXPIRY_KEY);

        if (!sessionData || !expiryTime) {
            return null;
        }

        // Check if session has expired
        if (Date.now() > parseInt(expiryTime)) {
            clearSession();
            return null;
        }

        return JSON.parse(sessionData) as User;
    } catch {
        return null;
    }
}

export function clearSession(): void {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(SESSION_EXPIRY_KEY);
    localStorage.removeItem(SESSION_LOGIN_TIME_KEY);
}

export function refreshSession(): void {
    const session = getSession();
    if (session) {
        // Extend session expiry
        const expiryTime = Date.now() + SESSION_EXPIRY_MS;
        localStorage.setItem(SESSION_EXPIRY_KEY, expiryTime.toString());
    }
}

export function getSessionTimeRemaining(): number {
    const expiryTime = localStorage.getItem(SESSION_EXPIRY_KEY);
    if (!expiryTime) return 0;

    const remaining = parseInt(expiryTime) - Date.now();
    return Math.max(0, remaining);
}

export function getSessionDuration(): number {
    const loginTime = localStorage.getItem(SESSION_LOGIN_TIME_KEY);
    if (!loginTime) return 0;

    return Math.floor((Date.now() - parseInt(loginTime)) / 1000); // Return seconds
}
