// TypeScript 6 부터 부수효과 import 의 모듈 해석을 요구하므로(TS2882),
// 전역 CSS import 를 위한 선언을 직접 둔다. Next 는 *.module.css 만 선언한다.
declare module '*.css'
