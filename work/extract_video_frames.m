#import <AVFoundation/AVFoundation.h>
#import <Foundation/Foundation.h>
#import <ImageIO/ImageIO.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

int main(int argc, const char *argv[]) {
  @autoreleasepool {
    if (argc < 3) return 1;
    NSString *sourcePath = [NSString stringWithUTF8String:argv[1]];
    NSString *outputPath = [NSString stringWithUTF8String:argv[2]];
    [[NSFileManager defaultManager] createDirectoryAtPath:outputPath withIntermediateDirectories:YES attributes:nil error:nil];
    AVURLAsset *asset = [AVURLAsset assetWithURL:[NSURL fileURLWithPath:sourcePath]];
    double duration = CMTimeGetSeconds(asset.duration);
    AVAssetImageGenerator *generator = [AVAssetImageGenerator assetImageGeneratorWithAsset:asset];
    generator.appliesPreferredTrackTransform = YES;
    generator.maximumSize = CGSizeMake(1600, 1600);
    double fractions[] = {0.0, 0.2, 0.4, 0.6, 0.8, 0.98};
    for (int i = 0; i < 6; i++) {
      CMTime time = CMTimeMakeWithSeconds(duration * fractions[i], 600);
      NSError *error = nil;
      CGImageRef image = [generator copyCGImageAtTime:time actualTime:nil error:&error];
      if (!image) {
        NSLog(@"%@", error);
        return 2;
      }
      NSString *name = [NSString stringWithFormat:@"frame-%02d.png", i];
      NSURL *destinationURL = [NSURL fileURLWithPath:[outputPath stringByAppendingPathComponent:name]];
      CGImageDestinationRef destination = CGImageDestinationCreateWithURL((__bridge CFURLRef)destinationURL, (__bridge CFStringRef)UTTypePNG.identifier, 1, nil);
      CGImageDestinationAddImage(destination, image, nil);
      CGImageDestinationFinalize(destination);
      CFRelease(destination);
      CGImageRelease(image);
    }
    printf("duration=%f\n", duration);
  }
  return 0;
}
