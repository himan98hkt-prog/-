//! 종단간 암호화 채널.
//!
//! - Noise XX 핸드셰이크로 양쪽 정적 공개키를 교환하고 세션키를 만든다.
//!   (클라이언트 = initiator, PC 에이전트 = responder)
//! - 이후에는 Noise 가 만든 두 방향 키로 메시지마다 ChaCha20-Poly1305 암호화.
//!   Noise 기본 전송 형식은 메시지 크기가 64KB 로 제한되어 화면 프레임에 맞지 않으므로
//!   같은 nonce 규칙(4바이트 0 + 카운터 u64 LE)을 쓰는 자체 AEAD 계층을 둔다.
//! - 핸드셰이크 해시에서 6자리 확인 코드(SAS)를 만든다. PC 와 휴대폰에 같은 숫자가
//!   보이면 중간자(중계 서버 포함)가 끼어들지 않았음이 보장된다.

use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce};
use sha2::{Digest, Sha256};
use thiserror::Error;

const NOISE_PARAMS: &str = "Noise_XX_25519_ChaChaPoly_BLAKE2s";
const PROLOGUE: &[u8] = b"HomePilot-Remote/1";
/// 하나의 암호화 메시지 최대 크기 (화면 프레임 포함). 이보다 크면 거부한다.
pub const MAX_MESSAGE: usize = 32 * 1024 * 1024;
const TAG_LEN: usize = 16;

#[derive(Debug, Error)]
pub enum SecureError {
    #[error("핸드셰이크 오류: {0}")]
    Noise(#[from] snow::Error),
    #[error("복호화 실패 (변조되었거나 순서가 어긋난 메시지)")]
    Decrypt,
    #[error("메시지가 너무 큼: {0} 바이트")]
    TooLarge(usize),
    #[error("핸드셰이크가 아직 끝나지 않음")]
    NotFinished,
    #[error("메시지 카운터 소진")]
    CounterExhausted,
    #[error("잘못된 키 형식")]
    BadKey,
}

pub type Result<T> = std::result::Result<T, SecureError>;

/// 장치/클라이언트의 고정 키쌍 (X25519).
#[derive(Clone)]
pub struct StaticKeypair {
    pub private: [u8; 32],
    pub public: [u8; 32],
}

impl std::fmt::Debug for StaticKeypair {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // 비밀키는 절대 로그에 남기지 않는다.
        f.debug_struct("StaticKeypair").field("public", &hex(&self.public)).finish_non_exhaustive()
    }
}

impl StaticKeypair {
    pub fn generate() -> Result<Self> {
        let kp = snow::Builder::new(NOISE_PARAMS.parse()?).generate_keypair()?;
        Ok(Self {
            private: kp.private.try_into().map_err(|_| SecureError::BadKey)?,
            public: kp.public.try_into().map_err(|_| SecureError::BadKey)?,
        })
    }

    pub fn from_bytes(private: &[u8], public: &[u8]) -> Result<Self> {
        Ok(Self {
            private: private.try_into().map_err(|_| SecureError::BadKey)?,
            public: public.try_into().map_err(|_| SecureError::BadKey)?,
        })
    }
}

/// 공개키에서 장치 ID(16진수 20자)를 만든다. 중계 서버 라우팅에 쓰인다.
pub fn device_id_from_public(public: &[u8; 32]) -> String {
    let digest = Sha256::digest(public);
    hex(&digest[..10])
}

/// 공개키 지문 (사용자에게 보여 주는 용도).
pub fn fingerprint(public: &[u8; 32]) -> String {
    let digest = Sha256::digest(public);
    hex(&digest[..8]).as_bytes().chunks(4).map(|c| std::str::from_utf8(c).unwrap_or("")).collect::<Vec<_>>().join("-")
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// 진행 중인 핸드셰이크.
pub struct Handshake {
    hs: snow::HandshakeState,
    initiator: bool,
}

impl Handshake {
    pub fn initiator(local: &StaticKeypair) -> Result<Self> {
        let hs = snow::Builder::new(NOISE_PARAMS.parse()?).local_private_key(&local.private).prologue(PROLOGUE).build_initiator()?;
        Ok(Self { hs, initiator: true })
    }

    pub fn responder(local: &StaticKeypair) -> Result<Self> {
        let hs = snow::Builder::new(NOISE_PARAMS.parse()?).local_private_key(&local.private).prologue(PROLOGUE).build_responder()?;
        Ok(Self { hs, initiator: false })
    }

    /// 다음 핸드셰이크 메시지를 만든다.
    pub fn write(&mut self) -> Result<Vec<u8>> {
        let mut buf = vec![0u8; 256];
        let n = self.hs.write_message(&[], &mut buf)?;
        buf.truncate(n);
        Ok(buf)
    }

    /// 상대의 핸드셰이크 메시지를 읽는다.
    pub fn read(&mut self, msg: &[u8]) -> Result<()> {
        let mut buf = vec![0u8; 256];
        self.hs.read_message(msg, &mut buf)?;
        Ok(())
    }

    pub fn is_finished(&self) -> bool {
        self.hs.is_handshake_finished()
    }

    pub fn finish(mut self) -> Result<SecureChannel> {
        if !self.hs.is_handshake_finished() {
            return Err(SecureError::NotFinished);
        }
        let remote: [u8; 32] = self.hs.get_remote_static().ok_or(SecureError::BadKey)?.try_into().map_err(|_| SecureError::BadKey)?;
        let sas = sas_from_hash(self.hs.get_handshake_hash());
        let (i2r, r2i) = self.hs.dangerously_get_raw_split();
        let (send_key, recv_key) = if self.initiator { (i2r, r2i) } else { (r2i, i2r) };
        Ok(SecureChannel {
            sealer: Sealer { aead: ChaCha20Poly1305::new(Key::from_slice(&send_key)), counter: 0 },
            opener: Opener { aead: ChaCha20Poly1305::new(Key::from_slice(&recv_key)), counter: 0 },
            remote_static: remote,
            sas,
        })
    }
}

fn sas_from_hash(hash: &[u8]) -> String {
    let n = u32::from_be_bytes([hash[0], hash[1], hash[2], hash[3]]) % 1_000_000;
    format!("{:03} {:03}", n / 1000, n % 1000)
}

fn nonce(counter: u64) -> [u8; 12] {
    let mut n = [0u8; 12];
    n[4..].copy_from_slice(&counter.to_le_bytes());
    n
}

/// 핸드셰이크가 끝난 암호화 채널.
pub struct SecureChannel {
    pub sealer: Sealer,
    pub opener: Opener,
    /// 상대방 정적 공개키 (등록 여부 확인용).
    pub remote_static: [u8; 32],
    /// 6자리 확인 코드 ("123 456").
    pub sas: String,
}

impl SecureChannel {
    pub fn into_split(self) -> (Sealer, Opener) {
        (self.sealer, self.opener)
    }
}

/// 보내는 쪽 암호화기.
pub struct Sealer {
    aead: ChaCha20Poly1305,
    counter: u64,
}

impl Sealer {
    pub fn seal(&mut self, plaintext: &[u8]) -> Result<Vec<u8>> {
        if plaintext.len() + TAG_LEN > MAX_MESSAGE {
            return Err(SecureError::TooLarge(plaintext.len()));
        }
        if self.counter == u64::MAX {
            return Err(SecureError::CounterExhausted);
        }
        let n = nonce(self.counter);
        self.counter += 1;
        self.aead.encrypt(Nonce::from_slice(&n), Payload { msg: plaintext, aad: &[] }).map_err(|_| SecureError::Decrypt)
    }
}

/// 받는 쪽 복호화기. 카운터가 순서대로 증가해야만 통과하므로 재전송(replay)이 차단된다.
pub struct Opener {
    aead: ChaCha20Poly1305,
    counter: u64,
}

impl Opener {
    pub fn open(&mut self, ciphertext: &[u8]) -> Result<Vec<u8>> {
        if ciphertext.len() > MAX_MESSAGE {
            return Err(SecureError::TooLarge(ciphertext.len()));
        }
        if self.counter == u64::MAX {
            return Err(SecureError::CounterExhausted);
        }
        let n = nonce(self.counter);
        let pt = self.aead.decrypt(Nonce::from_slice(&n), Payload { msg: ciphertext, aad: &[] }).map_err(|_| SecureError::Decrypt)?;
        self.counter += 1;
        Ok(pt)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn handshake() -> (SecureChannel, SecureChannel) {
        let ck = StaticKeypair::generate().unwrap();
        let ak = StaticKeypair::generate().unwrap();
        let mut c = Handshake::initiator(&ck).unwrap();
        let mut a = Handshake::responder(&ak).unwrap();
        a.read(&c.write().unwrap()).unwrap();
        c.read(&a.write().unwrap()).unwrap();
        a.read(&c.write().unwrap()).unwrap();
        assert!(c.is_finished() && a.is_finished());
        let cc = c.finish().unwrap();
        let ac = a.finish().unwrap();
        assert_eq!(cc.remote_static, ak.public);
        assert_eq!(ac.remote_static, ck.public);
        (cc, ac)
    }

    #[test]
    fn handshake_and_both_directions() {
        let (mut c, mut a) = handshake();
        assert_eq!(c.sas, a.sas);
        assert_eq!(c.sas.len(), 7);
        let ct = c.sealer.seal(b"hello").unwrap();
        assert_eq!(a.opener.open(&ct).unwrap(), b"hello");
        let big = vec![7u8; 3 * 1024 * 1024];
        let ct = a.sealer.seal(&big).unwrap();
        assert_eq!(c.opener.open(&ct).unwrap(), big);
    }

    #[test]
    fn replay_and_tamper_rejected() {
        let (mut c, mut a) = handshake();
        let ct1 = c.sealer.seal(b"one").unwrap();
        let ct2 = c.sealer.seal(b"two").unwrap();
        assert!(a.opener.open(&ct1).is_ok());
        // 같은 메시지를 다시 보내면 거부
        assert!(a.opener.open(&ct1).is_err());
        let mut bad = ct2.clone();
        bad[0] ^= 1;
        assert!(a.opener.open(&bad).is_err());
        assert_eq!(a.opener.open(&ct2).unwrap(), b"two");
    }

    #[test]
    fn mitm_changes_sas() {
        // 중간자가 양쪽과 따로 핸드셰이크하면 양쪽 SAS 가 달라진다.
        let ck = StaticKeypair::generate().unwrap();
        let ak = StaticKeypair::generate().unwrap();
        let mk = StaticKeypair::generate().unwrap();
        let mut c = Handshake::initiator(&ck).unwrap();
        let mut m_r = Handshake::responder(&mk).unwrap();
        m_r.read(&c.write().unwrap()).unwrap();
        c.read(&m_r.write().unwrap()).unwrap();
        m_r.read(&c.write().unwrap()).unwrap();
        let mut m_i = Handshake::initiator(&mk).unwrap();
        let mut a = Handshake::responder(&ak).unwrap();
        a.read(&m_i.write().unwrap()).unwrap();
        m_i.read(&a.write().unwrap()).unwrap();
        a.read(&m_i.write().unwrap()).unwrap();
        let c = c.finish().unwrap();
        let a = a.finish().unwrap();
        assert_ne!(c.remote_static, ak.public, "클라이언트는 PC 키 대신 중간자 키를 받음 → 고정키 비교로 탐지");
        assert_ne!(a.remote_static, ck.public);
    }

    #[test]
    fn device_id_format() {
        let k = StaticKeypair::generate().unwrap();
        let id = device_id_from_public(&k.public);
        assert!(crate::relay::is_valid_device_id(&id));
        assert_eq!(fingerprint(&k.public).len(), 19);
    }
}
