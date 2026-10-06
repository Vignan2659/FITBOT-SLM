// Render text to a WAV file with a macOS AVSpeechSynthesizer voice.
//   swift tts.swift <voice-identifier> <rate 0..1> <in.txt> <out.wav>
import AVFoundation
let a = CommandLine.arguments
guard a.count == 5, let voice = AVSpeechSynthesisVoice.speechVoices().first(where: { $0.identifier == a[1] }) else { print("usage / voice not found"); exit(2) }
let text = try String(contentsOfFile: a[3], encoding: .utf8)
let u = AVSpeechUtterance(string: text)
u.voice = voice
u.rate = Float(a[2])!
let synth = AVSpeechSynthesizer()
var file: AVAudioFile?
var frames = 0
let done = DispatchSemaphore(value: 0)
synth.write(u) { buf in
    guard let pcm = buf as? AVAudioPCMBuffer else { return }
    if pcm.frameLength == 0 { done.signal(); return }
    if file == nil {
        file = try? AVAudioFile(forWriting: URL(fileURLWithPath: a[4]), settings: pcm.format.settings,
                                commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved)
    }
    try? file?.write(from: pcm)
    frames += Int(pcm.frameLength)
}
_ = done.wait(timeout: .now() + 120)
print("frames:", frames)
exit(frames > 0 ? 0 : 1)
