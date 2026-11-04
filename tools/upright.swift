// Writes a photo as a JPEG with its pixels turned the right way up, using macOS's own
// image library, so every format (iPhone HEIC included) is handled the same way.
// Usage: swift tools/upright.swift input output.jpg
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count == 3,
      let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, nil),
      let props = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
      let width = props[kCGImagePropertyPixelWidth] as? Int,
      let height = props[kCGImagePropertyPixelHeight] as? Int else {
    FileHandle.standardError.write("Could not read photo\n".data(using: .utf8)!)
    exit(1)
}
let options: [CFString: Any] = [
    kCGImageSourceCreateThumbnailFromImageAlways: true,
    kCGImageSourceCreateThumbnailWithTransform: true,
    kCGImageSourceThumbnailMaxPixelSize: max(width, height),
]
guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary),
      let out = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL,
                                                UTType.jpeg.identifier as CFString, 1, nil) else {
    FileHandle.standardError.write("Could not convert photo\n".data(using: .utf8)!)
    exit(1)
}
CGImageDestinationAddImage(out, image, [kCGImageDestinationLossyCompressionQuality: 0.97] as CFDictionary)
if !CGImageDestinationFinalize(out) { exit(1) }
print(props[kCGImagePropertyOrientation] ?? 1, image.width, image.height)
