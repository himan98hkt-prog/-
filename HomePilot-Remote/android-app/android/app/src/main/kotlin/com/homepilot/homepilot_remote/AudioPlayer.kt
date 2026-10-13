package com.homepilot.homepilot_remote

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import java.nio.ByteBuffer
import java.util.ArrayDeque

/**
 * PC 소리 재생: AAC-LC ADTS (48kHz 스테레오) → MediaCodec 디코더 → AudioTrack.
 * 늦게 도착한 소리가 쌓이면(0.5초 이상) 오래된 것부터 버려 지연이 커지지 않게 한다.
 */
class AudioPlayer {
    private val thread = HandlerThread("hp-audio").apply { start() }
    private val h = Handler(thread.looper)
    private var codec: MediaCodec? = null
    private var track: AudioTrack? = null
    private val inputs = ArrayDeque<Int>()
    private val frames = ArrayDeque<ByteArray>()
    private var pts = 0L

    fun start(): Boolean = h.post {
        stopInternal()
        try {
            val rate = 48_000
            val fmt = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, 2)
            fmt.setInteger(MediaFormat.KEY_IS_ADTS, 1)
            // AudioSpecificConfig: AAC-LC(2), 48kHz(3), 스테레오(2)
            fmt.setByteBuffer("csd-0", ByteBuffer.wrap(byteArrayOf(0x11, 0x90.toByte())))
            val minBuf = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT)
            val t = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                .setAudioFormat(AudioFormat.Builder().setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setBufferSizeInBytes(minBuf * 2)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY)
                .build()
            t.play()
            track = t
            val c = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
            c.setCallback(object : MediaCodec.Callback() {
                override fun onInputBufferAvailable(codec: MediaCodec, index: Int) {
                    inputs.add(index)
                    feed()
                }

                override fun onOutputBufferAvailable(codec: MediaCodec, index: Int, info: MediaCodec.BufferInfo) {
                    try {
                        val out = codec.getOutputBuffer(index)
                        if (out != null && info.size > 0) {
                            out.position(info.offset)
                            out.limit(info.offset + info.size)
                            track?.write(out, info.size, AudioTrack.WRITE_NON_BLOCKING)
                        }
                        codec.releaseOutputBuffer(index, false)
                    } catch (_: Exception) {
                    }
                }

                override fun onError(codec: MediaCodec, e: MediaCodec.CodecException) {
                    Log.w(TAG, "소리 디코더 오류 → 재시작", e)
                    start()
                }

                override fun onOutputFormatChanged(codec: MediaCodec, format: MediaFormat) {}
            }, h)
            c.configure(fmt, null, null, 0)
            c.start()
            codec = c
        } catch (e: Exception) {
            Log.e(TAG, "소리 재생 시작 실패", e)
            stopInternal()
        }
    }

    /** PC 에서 온 묶음 (ADTS 프레임 여러 개) */
    fun feed(data: ByteArray): Boolean = h.post {
        if (codec == null) return@post
        splitAdts(data).forEach { frames.add(it) }
        // 약 0.5초(23 프레임) 넘게 밀리면 오래된 소리부터 버린다
        while (frames.size > 24) frames.poll()
        feed()
    }

    fun stop(): Boolean = h.post { stopInternal() }

    fun release(): Boolean = h.post {
        stopInternal()
        thread.quitSafely()
    }

    private fun feed() {
        val c = codec ?: return
        while (inputs.isNotEmpty() && frames.isNotEmpty()) {
            val idx = inputs.poll()!!
            val f = frames.poll()!!
            try {
                val buf = c.getInputBuffer(idx) ?: continue
                buf.clear()
                buf.put(f)
                pts += 21_333 // 1024 샘플 / 48kHz
                c.queueInputBuffer(idx, 0, f.size, pts, 0)
            } catch (e: Exception) {
                Log.w(TAG, "소리 입력 실패", e)
            }
        }
    }

    private fun stopInternal() {
        codec?.let {
            try {
                it.stop()
            } catch (_: Exception) {
            }
            it.release()
        }
        codec = null
        track?.let {
            try {
                it.stop()
            } catch (_: Exception) {
            }
            it.release()
        }
        track = null
        inputs.clear()
        frames.clear()
    }

    companion object {
        private const val TAG = "HomePilotAudio"

        /** ADTS 헤더의 frame_length(13비트)로 프레임을 나눈다. */
        fun splitAdts(data: ByteArray): List<ByteArray> {
            val out = ArrayList<ByteArray>()
            var i = 0
            while (i + 7 <= data.size) {
                if (data[i].toInt() and 0xFF != 0xFF || data[i + 1].toInt() and 0xF0 != 0xF0) {
                    i++ // 동기 신호를 찾을 때까지
                    continue
                }
                val len = ((data[i + 3].toInt() and 0x03) shl 11) or ((data[i + 4].toInt() and 0xFF) shl 3) or ((data[i + 5].toInt() and 0xE0) ushr 5)
                if (len < 7 || i + len > data.size) break
                out.add(data.copyOfRange(i, i + len))
                i += len
            }
            return out
        }
    }
}
