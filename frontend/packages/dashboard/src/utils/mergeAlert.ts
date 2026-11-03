import type { AlertMessage } from "../types/forecast";

/** Add an alert. ETA updates keep one card per shipment; the newest predictedAt wins. */
export function mergeAlert(
  prev: AlertMessage[],
  data: AlertMessage,
): AlertMessage[] {
  if (
    data.type !== "shipment-eta-update" ||
    !data.shipmentId ||
    !data.predictedAt
  ) {
    return [data, ...prev];
  }

  const incoming = Date.parse(data.predictedAt);
  if (!Number.isFinite(incoming)) return prev;

  const existing = prev.find(
    (a) =>
      a.type === "shipment-eta-update" &&
      a.shipmentId === data.shipmentId,
  );

  const existingTime = existing?.predictedAt
    ? Date.parse(existing.predictedAt)
    : NaN;

  if (Number.isFinite(existingTime) && incoming <= existingTime) {
    return prev;
  }

  return [
    data,
    ...prev.filter(
      (a) =>
        !(a.type === "shipment-eta-update" &&
          a.shipmentId === data.shipmentId),
    ),
  ];
}