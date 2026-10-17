// Extract text from a PDF using macOS PDFKit (JXA). Usage: osascript -l JavaScript pdftext.js in.pdf [firstPage lastPage]
ObjC.import('PDFKit');
ObjC.import('Foundation');
function run(argv) {
  var path = argv[0];
  var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(path));
  if (!doc || doc.isNil()) { return "ERROR: cannot open " + path; }
  var n = doc.pageCount;
  var a = argv.length > 1 ? parseInt(argv[1]) : 1;
  var b = argv.length > 2 ? parseInt(argv[2]) : n;
  var out = [];
  for (var i = a - 1; i < Math.min(b, n); i++) {
    var p = doc.pageAtIndex(i);
    var s = p.string;
    out.push("\n=== PAGE " + (i + 1) + " / " + n + " ===\n" + (s && !s.isNil() ? ObjC.unwrap(s) : ""));
  }
  return out.join("\n");
}
