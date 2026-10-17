import Foundation
import PDFKit
// Usage: swift pdf2txt.swift <input.pdf>  -> prints text to stdout
let args = CommandLine.arguments
guard args.count > 1 else { FileHandle.standardError.write("usage: pdf2txt <pdf>\n".data(using: .utf8)!); exit(1) }
let url = URL(fileURLWithPath: args[1])
guard let doc = PDFDocument(url: url) else { FileHandle.standardError.write("cannot open pdf\n".data(using: .utf8)!); exit(2) }
for i in 0..<doc.pageCount {
    if let p = doc.page(at: i), let s = p.string { print("\n=== PAGE \(i+1) ===\n" + s) }
}
