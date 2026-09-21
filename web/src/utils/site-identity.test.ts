import { describe, expect, it } from "vitest";
import { resolveBlogSiteIdentity } from "./site-identity";

describe("resolveBlogSiteIdentity", () => {
	it("引数なしはデフォルト値", () => {
		const r = resolveBlogSiteIdentity();
		expect(r.siteTitle).toBe("puppets records");
		expect(r.siteTagline).toBe("Electronic music label since 1989");
		expect(r.siteLogo).toBeNull();
		expect(r.siteFavicon).toBeNull();
	});

	it("titleとtagline上書き", () => {
		const r = resolveBlogSiteIdentity({ title: "My Site", tagline: "hello" });
		expect(r.siteTitle).toBe("My Site");
		expect(r.siteTagline).toBe("hello");
	});

	it("logo.urlありでlogoを返す", () => {
		const logo = { mediaId: "m1", url: "https://ex/logo.png", alt: "logo" };
		const r = resolveBlogSiteIdentity({ logo });
		expect(r.siteLogo).toBe(logo);
	});

	it("logo.urlなしはnull", () => {
		const r = resolveBlogSiteIdentity({ logo: { mediaId: "m1" } });
		expect(r.siteLogo).toBeNull();
	});

	it("faviconはurl文字列を返す", () => {
		const r = resolveBlogSiteIdentity({
			favicon: { mediaId: "m2", url: "https://ex/f.ico" },
		});
		expect(r.siteFavicon).toBe("https://ex/f.ico");
	});

	it("favicon.urlなしはnull", () => {
		const r = resolveBlogSiteIdentity({ favicon: { mediaId: "m2" } });
		expect(r.siteFavicon).toBeNull();
	});
});
