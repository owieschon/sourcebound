import {createHash} from 'node:crypto'
import {createProcessor} from '@mdx-js/mdx'
import remarkFrontmatter from 'remark-frontmatter'

const REQUEST_SCHEMA = 'clean-docs.mdx-parse-request.v1'
const SCHEMA = 'clean-docs.mdx-parse.v1'
const BATCH_SCHEMA = 'clean-docs.mdx-parse-batch.v1'

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = []
    process.stdin.on('data', (chunk) => chunks.push(chunk))
    process.stdin.on('error', reject)
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
  })
}

function position(node, source) {
  const start = node.position?.start
  const end = node.position?.end
  if (
    !start ||
    !end ||
    typeof start.offset !== 'number' ||
    typeof end.offset !== 'number'
  ) {
    throw new Error(`node ${node.type} has no source position`)
  }
  return {
    start: {
      line: start.line,
      column: start.column,
      byte: Buffer.byteLength(source.slice(0, start.offset)),
      offset: start.offset,
    },
    end: {
      line: end.line,
      column: end.column,
      byte: Buffer.byteLength(source.slice(0, end.offset)),
      offset: end.offset,
    },
  }
}

function plainText(node) {
  if (node.type === 'text' || node.type === 'inlineCode') {
    return node.value
  }
  if (!Array.isArray(node.children)) {
    return ''
  }
  return node.children.map(plainText).join('')
}

function mergedRanges(ranges) {
  const ordered = ranges
    .filter(([start, end]) => start < end)
    .sort((left, right) => left[0] - right[0] || left[1] - right[1])
  const result = []
  for (const range of ordered) {
    const previous = result.at(-1)
    if (!previous || range[0] > previous[1]) {
      result.push([...range])
    } else {
      previous[1] = Math.max(previous[1], range[1])
    }
  }
  return result
}

function residualRanges(node) {
  const outer = position(node, currentSource)
  const children = Array.isArray(node.children)
    ? mergedRanges(
        node.children.map((child) => {
          const childPosition = position(child, currentSource)
          return [childPosition.start.offset, childPosition.end.offset]
        }),
      )
    : []
  const result = []
  let cursor = outer.start.offset
  for (const [start, end] of children) {
    if (cursor < start) {
      result.push([cursor, start])
    }
    cursor = Math.max(cursor, end)
  }
  if (cursor < outer.end.offset) {
    result.push([cursor, outer.end.offset])
  }
  return result
}

function mask(source, ranges) {
  // mdast offsets and String#slice use UTF-16 code units. split('') keeps the
  // same indexing, including surrogate pairs, while spreading would not.
  const output = source.split('')
  for (const [start, end] of mergedRanges(ranges)) {
    for (let index = start; index < end; index += 1) {
      if (output[index] !== '\n' && output[index] !== '\r') {
        output[index] = ' '
      }
    }
  }
  return output.join('')
}

let currentSource = ''

function parseOne(source) {
  currentSource = source
  const processor = createProcessor({
    format: 'mdx',
    remarkPlugins: [remarkFrontmatter],
  })
  const tree = processor.parse(source)
  const definitions = new Map()
  const references = []
  const links = []
  const nodes = []
  const excluded = []

  function visit(node) {
    const located = position(node, source)
    const record = {
      type: node.type,
      start: located.start,
      end: located.end,
    }
    if (node.type === 'heading') {
      record.depth = node.depth
      record.text = plainText(node)
    } else if (node.type === 'code') {
      record.language = node.lang ?? null
      record.meta = node.meta ?? null
    } else if (node.type === 'image') {
      record.url = node.url
      record.alt = node.alt ?? null
    } else if (node.type === 'link') {
      record.url = node.url
      links.push({
        line: located.start.line,
        column: located.start.column,
        url: node.url,
      })
    } else if (node.type === 'definition') {
      definitions.set(node.identifier, node.url)
    } else if (node.type === 'linkReference') {
      references.push({
        identifier: node.identifier,
        line: located.start.line,
        column: located.start.column,
      })
    } else if (
      node.type === 'mdxJsxFlowElement' ||
      node.type === 'mdxJsxTextElement'
    ) {
      record.name = node.name
      excluded.push(...residualRanges(node))
    }
    if (
      node.type === 'code' ||
      node.type === 'yaml' ||
      node.type === 'mdxjsEsm' ||
      node.type === 'mdxFlowExpression' ||
      node.type === 'mdxTextExpression'
    ) {
      excluded.push([located.start.offset, located.end.offset])
    }
    if (
      node.type === 'heading' ||
      node.type === 'image' ||
      node.type === 'link' ||
      node.type === 'definition' ||
      node.type === 'code' ||
      node.type === 'yaml' ||
      node.type === 'mdxjsEsm' ||
      node.type === 'mdxFlowExpression' ||
      node.type === 'mdxTextExpression' ||
      node.type === 'mdxJsxFlowElement' ||
      node.type === 'mdxJsxTextElement'
    ) {
      nodes.push(record)
    }
    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        visit(child)
      }
    }
  }

  visit(tree)
  for (const reference of references) {
    const url = definitions.get(reference.identifier)
    if (url !== undefined) {
      links.push({...reference, url})
    }
  }
  return {
    schema: SCHEMA,
    parser: '@mdx-js/mdx@3.1.1',
    digest: createHash('sha256').update(source).digest('hex'),
    masked: mask(source, excluded),
    links: links.sort(
      (left, right) => left.line - right.line || left.column - right.column,
    ),
    nodes,
  }
}

async function main() {
  const request = JSON.parse(await readStdin())
  if (
    request?.schema !== REQUEST_SCHEMA ||
    !Array.isArray(request.documents)
  ) {
    throw new Error(`input must use ${REQUEST_SCHEMA}`)
  }
  const identifiers = new Set()
  const documents = []
  for (const item of request.documents) {
    if (
      typeof item?.id !== 'string' ||
      item.id.length === 0 ||
      typeof item?.text !== 'string' ||
      identifiers.has(item.id)
    ) {
      throw new Error('each MDX input needs a unique non-empty id and string text')
    }
    identifiers.add(item.id)
    try {
      documents.push({id: item.id, ok: true, result: parseOne(item.text)})
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      documents.push({id: item.id, ok: false, error: message})
    }
  }
  process.stdout.write(
    `${JSON.stringify({schema: BATCH_SCHEMA, documents})}\n`,
  )
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error)
  process.stderr.write(`${message}\n`)
  process.exitCode = 2
})
