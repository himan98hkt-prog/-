package com.homepilot.homepilot_remote

import android.media.MediaCodecList
import android.media.MediaFormat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val decoders = HashMap<Long, VideoDecoder>()

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val ch = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "homepilot/video")
        ch.setMethodCallHandler { call, result ->
            when (call.method) {
                // 이 휴대폰에 H.264 디코더가 있는지
                "supported" -> result.success(
                    MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.any { info ->
                        !info.isEncoder && info.supportedTypes.any { it.equals(MediaFormat.MIMETYPE_VIDEO_AVC, true) }
                    },
                )
                "create" -> {
                    val producer = flutterEngine.renderer.createSurfaceProducer()
                    val id = producer.id()
                    val dec = VideoDecoder(producer) { ch.invokeMethod("needKeyframe", id) }
                    decoders[id] = dec
                    dec.configure(call.argument<Int>("width")!!, call.argument<Int>("height")!!)
                    result.success(id)
                }
                "configure" -> {
                    decoders[call.argument<Number>("id")!!.toLong()]
                        ?.configure(call.argument<Int>("width")!!, call.argument<Int>("height")!!)
                    result.success(null)
                }
                "decode" -> {
                    decoders[call.argument<Number>("id")!!.toLong()]
                        ?.decode(call.argument<ByteArray>("data")!!, call.argument<Boolean>("key") == true)
                    result.success(null)
                }
                "dispose" -> {
                    decoders.remove(call.argument<Number>("id")!!.toLong())?.release()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onDestroy() {
        decoders.values.forEach { it.release() }
        decoders.clear()
        super.onDestroy()
    }
}
