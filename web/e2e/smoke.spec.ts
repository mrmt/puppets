import { expect, test } from "@playwright/test";

test.describe("スモークテスト", () => {
	for (const path of ["/", "/artists", "/posts", "/search", "/privacy", "/fa"]) {
		test(`${path} が200で表示される`, async ({ page }) => {
			const response = await page.goto(path);
			expect(response?.status()).toBe(200);
			await expect(page).toHaveTitle(/.+/);
		});
	}

	test("RSSがXMLで配信される", async ({ request }) => {
		const response = await request.get("/rss.xml");
		expect(response.status()).toBe(200);
		expect(response.headers()["content-type"] ?? "").toMatch(/xml/);
	});

	test("サイトマップがXMLで配信される", async ({ request }) => {
		const response = await request.get("/sitemap.xml");
		expect(response.status()).toBe(200);
		expect(await response.text()).toContain("<urlset");
	});

	test("存在しないパスは404を返す", async ({ page }) => {
		for (const path of ["/this-path-does-not-exist-xyz", "/posts/no-such-post", "/artists/no-such-artist", "/tag/no-such-tag"]) {
			const response = await page.goto(path);
			expect(response?.status(), path).toBe(404);
		}
	});

	test("旧 Tumblr URL は 301 で新 URL へ", async ({ request }) => {
		const cases: [string, string][] = [
			["/post/821889724426977280/diastereomer35", "/posts/diastereomer-35-primrose"],
			["/tagged/sectcommune", "/artists/sect-commune"],
			["/tagged/live", "/tag/live"],
			["/rss", "/rss.xml"],
			["/archive", "/posts"],
		];
		for (const [from, to] of cases) {
			const response = await request.get(from, { maxRedirects: 0 });
			expect(response.status(), from).toBe(301);
			expect(new URL(response.headers().location ?? "", "http://x").pathname, from).toBe(to);
		}
	});

	test("未知の旧投稿 ID は404", async ({ request }) => {
		const response = await request.get("/post/1/unknown", { maxRedirects: 0 });
		expect(response.status()).toBe(404);
	});
});
