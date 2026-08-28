import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Props {
  content: string
}

/**
 * Renders Markdown.
 *
 * react-markdown builds a React element tree rather than setting innerHTML,
 * and raw HTML inside the Markdown is ignored because `rehype-raw` is not
 * installed. Embedded HTML is therefore inert by construction.
 */
export function MarkdownRenderer({ content }: Props) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
