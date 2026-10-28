// ocr-image — on-device OCR via Apple's Vision framework. No deps, no GUI, no cloud.
// Usage: ocr-image <image1> [image2 ...]   → prints recognized text to stdout.
// Build: swiftc -O extras/ocr-image.swift -o extras/ocr-image   (install.sh does this for you)
import Foundation
import Vision
import AppKit

func ocr(_ path: String) -> String {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("ocr-image: cannot read \(path)\n".data(using: .utf8)!)
        return ""
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch {
        FileHandle.standardError.write("ocr-image: \(error)\n".data(using: .utf8)!)
        return ""
    }
    let obs = req.results ?? []
    return obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

let args = Array(CommandLine.arguments.dropFirst())
if args.isEmpty { FileHandle.standardError.write("usage: ocr-image <image...>\n".data(using: .utf8)!); exit(2) }
for p in args { print(ocr(p)) }
