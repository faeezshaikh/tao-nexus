// Query history – localStorage CRUD
import { HistoryEntry } from "../types/finops";

const STORAGE_KEY = "tao_lens_query_history";
const MAX_ENTRIES = 25;

/** Prepend a new entry and trim to MAX_ENTRIES. */
export function saveHistoryEntry(entry: HistoryEntry): void {
    const history = getHistory();
    history.unshift(entry);
    if (history.length > MAX_ENTRIES) history.length = MAX_ENTRIES;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

/** Return all saved entries, newest-first. */
export function getHistory(): HistoryEntry[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        return JSON.parse(raw) as HistoryEntry[];
    } catch {
        return [];
    }
}

/** Look up a single entry by id. */
export function getHistoryEntry(id: string): HistoryEntry | null {
    return getHistory().find((e) => e.id === id) ?? null;
}

/** Remove a single entry by id. */
export function deleteHistoryEntry(id: string): void {
    const history = getHistory().filter((e) => e.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

/** Remove all history entries. */
export function clearHistory(): void {
    localStorage.removeItem(STORAGE_KEY);
}
