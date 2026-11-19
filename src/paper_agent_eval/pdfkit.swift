import Foundation
import PDFKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
func fail(_ kind: String) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: ["error": kind])
    FileHandle.standardOutput.write(data)
    exit(0)
}
guard let doc = PDFDocument(url: url) else { fail("corrupt_pdf") }
if doc.isEncrypted { fail("encrypted_pdf") }
if doc.pageCount > 200 { fail("page_limit_exceeded") }
var pages: [String] = []
for i in 0..<doc.pageCount { pages.append(doc.page(at: i)?.string ?? "") }
let output: [String: Any] = ["pages": pages, "parser": "PDFKit/" + (Bundle(for: PDFDocument.self).infoDictionary?["CFBundleVersion"] as? String ?? "unknown"), "os": ProcessInfo.processInfo.operatingSystemVersionString]
let data = try JSONSerialization.data(withJSONObject: output)
FileHandle.standardOutput.write(data)
