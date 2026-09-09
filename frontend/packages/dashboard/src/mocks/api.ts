import { forecast } from "./forecast";
import { inventory } from "./inventory";

const delay = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });

export const fetchForecast = async () => {
  await delay(1000);
  return forecast;
};

export const fetchInventory = async () => {
  await delay(1000);
  return inventory;
};