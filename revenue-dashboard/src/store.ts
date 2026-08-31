import { create } from "zustand";

import type { BookingPerformanceRow, InquiryRow, PropertyPerformanceRow } from "./types";

type UploadMeta = { fileName: string; uploadedAt: string };

type RevenueAnalyticsState = {
  propertyRows: PropertyPerformanceRow[];
  propertyMeta: UploadMeta | null;
  bookingRows: BookingPerformanceRow[];
  bookingMeta: UploadMeta | null;
  inquiryRows: InquiryRow[];
  inquiryMeta: UploadMeta | null;
  setPropertyData: (rows: PropertyPerformanceRow[], meta: UploadMeta) => void;
  setBookingData: (rows: BookingPerformanceRow[], meta: UploadMeta) => void;
  setInquiryData: (rows: InquiryRow[], meta: UploadMeta) => void;
  clearProperty: () => void;
  clearBooking: () => void;
  clearInquiry: () => void;
};

export const useRevenueAnalyticsStore = create<RevenueAnalyticsState>((set) => ({
  propertyRows: [],
  propertyMeta: null,
  bookingRows: [],
  bookingMeta: null,
  inquiryRows: [],
  inquiryMeta: null,
  setPropertyData: (rows, meta) => set({ propertyRows: rows, propertyMeta: meta }),
  setBookingData: (rows, meta) => set({ bookingRows: rows, bookingMeta: meta }),
  setInquiryData: (rows, meta) => set({ inquiryRows: rows, inquiryMeta: meta }),
  clearProperty: () => set({ propertyRows: [], propertyMeta: null }),
  clearBooking: () => set({ bookingRows: [], bookingMeta: null }),
  clearInquiry: () => set({ inquiryRows: [], inquiryMeta: null }),
}));
