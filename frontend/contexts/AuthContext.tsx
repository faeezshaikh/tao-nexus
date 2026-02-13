"use client";

import { createContext, useContext, useState, useEffect, ReactNode, useRef } from "react";
import { User, getSession, clearSession, refreshSession } from "../lib/auth";

interface AuthContextType {
    user: User | null;
    login: (user: User) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const userRef = useRef<User | null>(null);

    // Update ref when user changes
    useEffect(() => {
        userRef.current = user;
    }, [user]);

    useEffect(() => {
        // Check for existing session on mount
        const session = getSession();
        setUser(session);
        setIsLoading(false);

        // Set up session expiry check interval (every 30 seconds)
        const interval = setInterval(() => {
            const currentSession = getSession();
            if (!currentSession && userRef.current) {
                // Session expired
                setUser(null);
            }
        }, 30000);

        return () => clearInterval(interval);
    }, []); // Empty dependency array - only run on mount

    // Refresh session on user activity
    useEffect(() => {
        if (!user) return;

        const handleActivity = () => {
            refreshSession();
        };

        window.addEventListener("mousemove", handleActivity);
        window.addEventListener("keydown", handleActivity);
        window.addEventListener("click", handleActivity);

        return () => {
            window.removeEventListener("mousemove", handleActivity);
            window.removeEventListener("keydown", handleActivity);
            window.removeEventListener("click", handleActivity);
        };
    }, [user]);

    const login = (user: User) => {
        setUser(user);
    };

    const logout = () => {
        clearSession();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
