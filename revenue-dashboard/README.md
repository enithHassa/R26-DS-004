# Tonik Revenue Analytics Dashboard

Standalone weekly revenue reporting dashboard with CSV upload for:

- **Property performance** — occupancy, room revenue, targets, Tonik share
- **Booking performance** — country, channel, and property charts
- **Inquiries** — channel breakdown with date range filters

## Quick start

```bash
cd revenue-dashboard
npm install
npm run dev
```

Opens at [http://localhost:5174](http://localhost:5174).

## CSV uploads

Each tab accepts a CSV file. Sample templates are in `public/revenue-analytics/samples/` and downloadable from the UI.

| Section | Required columns |
|---------|------------------|
| Property | `property`, `month`, `booked_room_nights`, `available_days`, `sellable_room_nights`, `occupancy`, `room_revenue`, `monthly_target`, `tonik_share` |
| Booking | `booking_date`, `property`, `country`, `channel`, `room_nights`, `room_revenue` |
| Inquiries | `inquiry_date`, `channel`, `inquiries` |

Column aliases (e.g. `brns`, `occ`) are supported. Export Excel sheets to CSV before upload.

## Build

```bash
npm run build
npm run preview
```

Static output is written to `dist/`.
