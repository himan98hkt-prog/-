package expo.modules.cardocr

import android.app.Activity
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import java.io.File
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import expo.modules.kotlin.Promise
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

/**
 * 명함 사진의 글자를 휴대폰 안에서 읽는다 (Google ML Kit, 무료·오프라인).
 * 줄 단위 텍스트와 위치·크기를 돌려주면 JS 쪽(src/core/cardParser.ts)이 이름·회사·전화 등으로 나눈다.
 */
class CardOcrModule : Module() {
  private val recognizer by lazy {
    TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())
  }

  /** 문서 스캐너 결과를 기다리는 중인 요청 */
  private var pendingScan: Promise? = null

  override fun definition() = ModuleDefinition {
    Name("CardOcr")

    /**
     * Google 문서 스캐너(Play 서비스, 무료)로 명함을 찍는다 — 테두리 자동 인식, 기울기·원근 보정, 그림자 제거.
     * pageLimit=2 면 앞면·뒷면을 한 번에. 찍은 쪽 JPEG 경로 목록을 돌려주고, 취소하면 빈 목록.
     */
    AsyncFunction("scanDocumentAsync") { pageLimit: Int, promise: Promise ->
      val activity = appContext.currentActivity
      if (activity == null) {
        promise.reject("E_ACTIVITY", "화면을 찾을 수 없습니다", null)
      } else if (pendingScan != null) {
        promise.reject("E_BUSY", "이미 촬영 중입니다", null)
      } else {
        val options = GmsDocumentScannerOptions.Builder()
          .setGalleryImportAllowed(true)
          .setPageLimit(pageLimit.coerceIn(1, 2))
          .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
          .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
          .build()
        GmsDocumentScanning.getClient(options)
          .getStartScanIntent(activity)
          .addOnSuccessListener { intentSender ->
            pendingScan = promise
            try {
              activity.startIntentSenderForResult(intentSender, SCAN_REQUEST, null, 0, 0, 0)
            } catch (e: Exception) {
              pendingScan = null
              promise.reject("E_SCANNER", e.message ?: "문서 스캐너를 열 수 없습니다", e)
            }
          }
          .addOnFailureListener { e ->
            promise.reject("E_SCANNER", e.message ?: "문서 스캐너를 쓸 수 없습니다", e)
          }
      }
    }

    OnActivityResult { _, (requestCode, resultCode, data) ->
      if (requestCode != SCAN_REQUEST) return@OnActivityResult
      val promise = pendingScan ?: return@OnActivityResult
      pendingScan = null
      if (resultCode != Activity.RESULT_OK) {
        promise.resolve(emptyList<String>())
        return@OnActivityResult
      }
      try {
        val context = appContext.reactContext ?: throw IllegalStateException("앱 컨텍스트 없음")
        val pages = GmsDocumentScanningResult.fromActivityResultIntent(data)?.pages ?: emptyList()
        val stamp = System.currentTimeMillis()
        // 스캐너가 준 주소를 앱 캐시의 일반 파일로 옮겨 이후 단계(리사이즈·인식·보관)가 그대로 쓰게 한다
        val uris = pages.mapIndexed { i, page ->
          val out = File(context.cacheDir, "cardscan-$stamp-$i.jpg")
          context.contentResolver.openInputStream(page.imageUri).use { input ->
            requireNotNull(input) { "스캔 이미지를 열 수 없습니다" }
            out.outputStream().use { input.copyTo(it) }
          }
          Uri.fromFile(out).toString()
        }
        promise.resolve(uris)
      } catch (e: Exception) {
        promise.reject("E_SCANNER", e.message ?: "스캔 결과를 읽지 못했습니다", e)
      }
    }

    AsyncFunction("recognizeAsync") { uri: String, promise: Promise ->
      val context = appContext.reactContext
      if (context == null) {
        promise.reject("E_CONTEXT", "앱 컨텍스트를 찾을 수 없습니다", null)
      } else {
        try {
          val image = InputImage.fromFilePath(context, Uri.parse(uri))
          recognizer.process(image)
            .addOnSuccessListener { result ->
              val lines = ArrayList<Map<String, Any>>()
              result.textBlocks.forEachIndexed { blockIndex, block ->
                for (line in block.lines) {
                  val box = line.boundingBox
                  lines.add(
                    mapOf(
                      "text" to line.text,
                      "block" to blockIndex,
                      "left" to (box?.left ?: 0),
                      "top" to (box?.top ?: 0),
                      "width" to (box?.width() ?: 0),
                      "height" to (box?.height() ?: 0)
                    )
                  )
                }
              }
              promise.resolve(
                mapOf(
                  "text" to result.text,
                  "lines" to lines,
                  "width" to image.width,
                  "height" to image.height
                )
              )
            }
            .addOnFailureListener { e ->
              promise.reject("E_OCR", e.message ?: "문자 인식에 실패했습니다", e)
            }
        } catch (e: Exception) {
          promise.reject("E_IMAGE", "이미지를 열 수 없습니다: ${e.message}", e)
        }
      }
    }
  }

  companion object {
    private const val SCAN_REQUEST = 7301
  }
}
