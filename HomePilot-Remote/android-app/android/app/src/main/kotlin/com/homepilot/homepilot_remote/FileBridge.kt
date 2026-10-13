package com.homepilot.homepilot_remote

import android.app.Activity
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileInputStream

/**
 * 파일 주고받기용 휴대폰 기능 (별도 플러그인 없이 Android 기본 기능만 사용).
 * - pickFile: 보낼 파일 고르기 → 앱 임시 폴더로 복사해 경로를 돌려준다 (저장소 권한 불필요)
 * - saveToDownloads: 받은 파일을 휴대폰 '다운로드/HomePilot' 에 저장 (Android 10+ 는 권한 불필요)
 * - open: 받은 파일 열기
 */
class FileBridge(private val activity: Activity) {
    private var pending: MethodChannel.Result? = null

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "pickFile" -> {
                if (pending != null) {
                    result.error("busy", "이미 파일을 고르는 중입니다", null)
                    return
                }
                pending = result
                val i = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                }
                activity.startActivityForResult(i, REQ_PICK)
            }
            "saveToDownloads" -> {
                try {
                    result.success(save(call.argument<String>("src")!!, call.argument<String>("name")!!))
                } catch (e: Exception) {
                    result.error("save", e.message, null)
                }
            }
            "open" -> {
                try {
                    val uri = Uri.parse(call.argument<String>("uri")!!)
                    val mime = mimeOf(call.argument<String>("name") ?: "")
                    activity.startActivity(
                        Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),
                    )
                    result.success(true)
                } catch (e: Exception) {
                    result.success(false) // 열 수 있는 앱이 없음
                }
            }
            else -> result.notImplemented()
        }
    }

    /** MainActivity.onActivityResult 에서 호출. 처리했으면 true. */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode != REQ_PICK) return false
        android.util.Log.i("HomePilotFiles", "파일 선택 결과 code=$resultCode uri=${data?.data} pending=${pending != null}")
        val r = pending ?: return true
        pending = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            r.success(null) // 취소
            return true
        }
        Thread {
            try {
                var name = "파일"
                activity.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                    if (c.moveToFirst()) name = c.getString(0) ?: name
                }
                val dir = File(activity.cacheDir, "upload").apply { mkdirs() }
                dir.listFiles()?.forEach { it.delete() } // 이전 임시 파일 정리
                val out = File(dir, name.replace('/', '_'))
                activity.contentResolver.openInputStream(uri)!!.use { inp -> out.outputStream().use { inp.copyTo(it) } }
                activity.runOnUiThread { r.success(mapOf("path" to out.absolutePath, "name" to name, "size" to out.length())) }
            } catch (e: Exception) {
                activity.runOnUiThread { r.error("pick", e.message, null) }
            }
        }.start()
        return true
    }

    private fun mimeOf(name: String): String {
        val ext = name.substringAfterLast('.', "").lowercase()
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"
    }

    /** 받은 파일(앱 임시 폴더)을 다운로드/HomePilot 으로 옮기고 열 수 있는 주소를 돌려준다. */
    private fun save(src: String, name: String): String {
        val f = File(src)
        if (Build.VERSION.SDK_INT >= 29) {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mimeOf(name))
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/HomePilot")
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val resolver = activity.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)!!
            resolver.openOutputStream(uri)!!.use { out -> FileInputStream(f).use { it.copyTo(out) } }
            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            f.delete()
            return uri.toString()
        }
        // Android 9 이하: 앱 전용 다운로드 폴더 (권한 불필요)
        val dir = File(activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "HomePilot").apply { mkdirs() }
        val out = File(dir, name)
        f.copyTo(out, overwrite = true)
        f.delete()
        return Uri.fromFile(out).toString()
    }

    companion object {
        private const val REQ_PICK = 4711
    }
}
