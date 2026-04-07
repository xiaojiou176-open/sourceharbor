import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { sanitizeExternalUrl } from "@/lib/api/url";

type MarkdownPreviewProps = {
	markdown: string;
};

export function MarkdownPreview({ markdown }: MarkdownPreviewProps) {
	const components: Components = {
		a: ({ href, children, ...props }) => {
			const safeHref = href ? sanitizeExternalUrl(href) : null;
			if (!safeHref) {
				return <span {...props}>{children}</span>;
			}
			return (
				<a href={safeHref} target="_blank" rel="noreferrer noopener" {...props}>
					{children}
				</a>
			);
		},
	};

	return (
		<article className="markdown-body">
			<ReactMarkdown
				skipHtml
				remarkPlugins={[remarkGfm]}
				disallowedElements={["script", "style", "iframe", "object", "embed"]}
				components={components}
			>
				{markdown}
			</ReactMarkdown>
		</article>
	);
}
