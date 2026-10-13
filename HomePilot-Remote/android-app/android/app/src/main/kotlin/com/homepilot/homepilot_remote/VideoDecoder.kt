package com.homepilot.homepilot_remote

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log
import io.flutter.view.TextureRegistry
import java.util.ArrayDeque

/**
 * H.264 하드웨어 디코더 (MediaCodec 비동기 모드) → Flutter 텍스처에 바로 그린다.
 *
 * - PC 에서 온 Annex-B 프레임을 순서대로 넣는다.
 * - 처음·오류·화면 표면 재생성 때는 키프레임부터 다시 시작해야 하므로 [onNeedKeyframe] 로 요청한다.
 */
class VideoDecoder(
    private val producer: TextureRegistry.SurfaceProducer,
    private val onNeedKeyframe: () -> Unit,
) {
    private val thread = HandlerThread("hp-video").apply { start() }
    private val h = Handler(thread.looper)
    private val main = Handler(Looper.getMainLooper())
    private var codec: MediaCodec? = null
    private var width = 0
    private var height = 0
    private var needKey = true
    private val inputs = ArrayDeque<Int>()
    private val pending = ArrayDeque<Pair<ByteArray, Boolean>>()
    private var pts = 0L

    init {
        producer.setCallback(object : TextureRegistry.SurfaceProducer.Callback {
            override fun onSurfaceAvailable() {
                // 앱이 백그라운드에서 돌아오면 표면이 새로 만들어진다 → 디코더 재시작
                h.post { if (width > 0) start(width, height) }
            }

            override fun onSurfaceCleanup() {
                h.post { stop() }
            }
        })
    }

    fun configure(w: Int, hgt: Int) = h.post { if (w != width || hgt != height || codec == null) start(w, hgt) }

    fun decode(data: ByteArray, key: Boolean) = h.post {
        if (codec == null) return@post
        if (needKey && !key) return@post // 키프레임 전에는 화면을 만들 수 없음
        needKey = false
        pending.add(data to key)
        if (pending.size > 30) {
            // 디코더가 너무 밀림 → 비우고 키프레임부터
            pending.clear()
            needKey = true
            requestKey()
            return@post
        }
        feed()
    }

    fun release() = h.post {
        stop()
        producer.release()
        thread.quitSafely()
    }

    private fun requestKey() = main.post { onNeedKeyframe() }

    private fun start(w: Int, hgt: Int) {
        stop()
        width = w
        height = hgt
        try {
            producer.setSize(w, hgt)
            val fmt = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, w, hgt)
            if (Build.VERSION.SDK_INT >= 30) fmt.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
            fmt.setInteger(MediaFormat.KEY_PRIORITY, 0) // 실시간
            val c = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            c.setCallback(object : MediaCodec.Callback() {
                override fun onInputBufferAvailable(codec: MediaCodec, index: Int) {
                    inputs.add(index)
                    feed()
                }

                override fun onOutputBufferAvailable(codec: MediaCodec, index: Int, info: MediaCodec.BufferInfo) {
                    try {
                        codec.releaseOutputBuffer(index, true) // 바로 화면에 그림
                    } catch (_: Exception) {
                    }
                }

                override fun onError(codec: MediaCodec, e: MediaCodec.CodecException) {
                    Log.w(TAG, "디코더 오류 → 재시작", e)
                    h.post { start(width, height) }
                }

                override fun onOutputFormatChanged(codec: MediaCodec, format: MediaFormat) {}
            }, h)
            c.configure(fmt, producer.surface, null, 0)
            c.start()
            codec = c
            needKey = true
            requestKey()
        } catch (e: Exception) {
            Log.e(TAG, "디코더 시작 실패", e)
            codec = null
        }
    }

    private fun feed() {
        val c = codec ?: return
        while (inputs.isNotEmpty() && pending.isNotEmpty()) {
            val idx = inputs.poll()!!
            val (data, key) = pending.poll()!!
            try {
                val buf = c.getInputBuffer(idx) ?: continue
                buf.clear()
                if (data.size > buf.capacity()) {
                    // 입력 버퍼보다 큰 프레임(드묾) → 버리고 키프레임부터
                    c.queueInputBuffer(idx, 0, 0, pts, 0)
                    needKey = true
                    requestKey()
                    continue
                }
                buf.put(data)
                pts += 33_333
                c.queueInputBuffer(idx, 0, data.size, pts, if (key) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0)
            } catch (e: Exception) {
                Log.w(TAG, "프레임 입력 실패", e)
                needKey = true
                requestKey()
            }
        }
    }

    private fun stop() {
        val c = codec ?: return
        codec = null
        inputs.clear()
        pending.clear()
        try {
            c.stop()
        } catch (_: Exception) {
        }
        c.release()
    }

    companion object {
        private const val TAG = "HomePilotVideo"
    }
}
