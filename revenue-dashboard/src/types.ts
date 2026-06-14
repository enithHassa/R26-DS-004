export type PropertyPerformanceRow = {
  property: string;
  month: string;
  bookedRoomNights: number | null;
  availableDays: number | null;
  sellableRoomNights: number | null;
  occupancy: number | null;
  roomRevenue: number | null;
  monthlyTarget: number | null;
  tonikShare: number | null;
};

export type BookingPerformanceRow = {
  bookingDate: string;
  property: string;
  country: string;
  channel: string;
  roomNights: number;
  roomRevenue: number;
};

export type InquiryRow = {
  inquiryDate: string;
  channel: string;
  inquiries: number;
  property?: string;
};

export type CsvParseResult<T> =
  | { ok: true; rows: T[]; warnings: string[] }
  | { ok: false; error: string };
