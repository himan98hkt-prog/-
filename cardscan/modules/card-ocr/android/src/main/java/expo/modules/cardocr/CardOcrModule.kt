package expo.modules.cardocr

import android.net.Uri
import com.google.mlkit.vision.common.InputImage
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

  override fun definition() = ModuleDefinition {
    Name("CardOcr")

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
}
