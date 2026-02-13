export type ChartSeries = {
    name: string;
    values: number[];
};

export type ChartData = {
    type: "line" | "bar";
    x: string[];
    series: ChartSeries[];
};

export type TableData = {
    columns: string[];
    rows: (string | number)[][];
};

export type FinopsResponse = {
    table: TableData;
    chart: ChartData;
    summary: string;
};

export interface HistoryEntry {
    id: string;
    query: string;
    username: string;
    timestamp: string;      // ISO 8601
    durationMs: number;
    response: FinopsResponse;
}
