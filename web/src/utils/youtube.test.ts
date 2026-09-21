import { describe, expect, it } from "vitest";

import { youtubeEmbedUrl, youtubeId, youtubeThumbnail } from "./youtube";

describe("youtubeId", () => {
	it.each([
		["https://www.youtube.com/watch?v=utfWl60tUoI", "utfWl60tUoI"],
		["https://www.youtube.com/watch?feature=shared&v=utfWl60tUoI", "utfWl60tUoI"],
		["https://youtu.be/utfWl60tUoI?t=10", "utfWl60tUoI"],
		["https://www.youtube.com/embed/utfWl60tUoI", "utfWl60tUoI"],
		["https://www.youtube-nocookie.com/embed/utfWl60tUoI", "utfWl60tUoI"],
		["https://www.youtube.com/shorts/utfWl60tUoI", "utfWl60tUoI"],
	])("%s", (url, id) => {
		expect(youtubeId(url)).toBe(id);
	});

	it("YouTube 以外と空値は null", () => {
		expect(youtubeId("https://vimeo.com/12345")).toBeNull();
		expect(youtubeId("")).toBeNull();
		expect(youtubeId(undefined)).toBeNull();
	});
});

describe("URL 生成", () => {
	it("埋め込みは nocookie ドメイン", () => {
		expect(youtubeEmbedUrl("abc")).toBe("https://www.youtube-nocookie.com/embed/abc");
	});
	it("サムネイル", () => {
		expect(youtubeThumbnail("abc")).toBe("https://i.ytimg.com/vi/abc/hqdefault.jpg");
	});
});
