import AVFoundation
import Foundation
import ImageIO
import UniformTypeIdentifiers

let source = URL(fileURLWithPath: CommandLine.arguments[1])
let outputDirectory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let asset = AVURLAsset(url: source)
let duration = CMTimeGetSeconds(asset.duration)
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.maximumSize = CGSize(width: 1600, height: 1600)

try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)

for (index, fraction) in [0.0, 0.2, 0.4, 0.6, 0.8, 0.98].enumerated() {
    let time = CMTime(seconds: max(duration * fraction, 0), preferredTimescale: 600)
    let image = try generator.copyCGImage(at: time, actualTime: nil)
    let destinationURL = outputDirectory.appendingPathComponent(String(format: "frame-%02d.png", index))
    guard let destination = CGImageDestinationCreateWithURL(destinationURL as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fatalError("Unable to create image destination")
    }
    CGImageDestinationAddImage(destination, image, nil)
    CGImageDestinationFinalize(destination)
}

print("duration=\(duration)")
