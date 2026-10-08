/// <reference types="node" />

import { test, expect } from "@playwright/test";

const username = process.env.TEST_AUTH_USERNAME ?? "";
const password = process.env.TEST_AUTH_PASSWORD ?? "";

test("logs in successfully with real credentials", async ({ page }) => {
page.on("console", (message) => {
console.log("BROWSER:", message.text());
});

page.on("pageerror", (error) => {
console.log("PAGE ERROR:", error.message);
});

page.on("request", (request) => {
if (request.url().includes("/api/v1/auth")) {
console.log("AUTH REQUEST:", request.method(), request.url());
}
});

page.on("response", (response) => {
if (response.url().includes("/api/v1/auth")) {
console.log("AUTH RESPONSE:", response.status(), response.url());
}
});

await page.goto("/");

await page.getByPlaceholder("Email").fill(username);
await page.getByPlaceholder("Password").fill(password);

const button = page.getByRole("button", { name: "Sign in" });

console.log("BUTTON TYPE:", await button.getAttribute("type"));
console.log("BUTTON FORM:", await button.getAttribute("form"));
console.log("FORM COUNT:", await page.locator("form").count());

console.log(
"FORM HTML:",
await page.locator("form").first().evaluate((form) => form.outerHTML),
);

await button.click();

await expect(
page.getByRole("heading", { name: "Executive Dashboard" }),
).toBeVisible({ timeout: 10000 });
});

test("shows an error for invalid password", async ({ page }) => {
page.on("console", (message) => {
console.log("BROWSER:", message.text());
});

page.on("pageerror", (error) => {
console.log("PAGE ERROR:", error.message);
});

page.on("request", (request) => {
if (request.url().includes("/api/v1/auth")) {
console.log("AUTH REQUEST:", request.method(), request.url());
}
});

page.on("response", (response) => {
if (response.url().includes("/api/v1/auth")) {
console.log("AUTH RESPONSE:", response.status(), response.url());
}
});

await page.goto("/");

await page.getByPlaceholder("Email").fill(username);
await page.getByPlaceholder("Password").fill("invalid-password");

const button = page.getByRole("button", { name: "Sign in" });

console.log("BUTTON TYPE:", await button.getAttribute("type"));
console.log("BUTTON FORM:", await button.getAttribute("form"));
console.log("FORM COUNT:", await page.locator("form").count());

console.log(
"FORM HTML:",
await page.locator("form").first().evaluate((form) => form.outerHTML),
);

await button.click();

await expect(page.getByRole("alert")).toBeVisible({ timeout: 10000 });
});
