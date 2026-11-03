import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { Button, Card, Field } from '../../components/ui'
import * as Ic from '../../components/Icons'
import { useAuth } from '../../auth'

export default function Index() {
  const { me, refresh } = useAuth()
  const navigate = useNavigate()
  const video = useRef(null)
  const stream = useRef(null)
  const starting = useRef(false)
  const mounted = useRef(true)
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [paused, setPaused] = useState(false)

  function stop() {
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
    if (video.current) video.current.srcObject = null
    setReady(false)
  }

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      stream.current?.getTracks().forEach(track => track.stop())
    }
  }, [])

  useEffect(() => {
    if (me !== undefined && !me?.face_user_id) {
      setPaused(false)
      start()
    }
    if (me?.face_user_id) stop()
  }, [me === undefined, me?.id, me?.face_user_id])

  async function start() {
    if (starting.current || stream.current) return
    starting.current = true
    setPaused(false)
    setMessage('')
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('카메라는 localhost 또는 HTTPS에서 사용할 수 있습니다.')
      }
      const camera = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: 640, height: 480 }, audio: false,
      })
      if (!mounted.current || !video.current) {
        camera.getTracks().forEach(track => track.stop())
        return
      }
      stream.current = camera
      video.current.srcObject = camera
      await video.current.play()
      setReady(true)
    } catch (error) {
      stop()
      setMessage(error.name === 'NotAllowedError'
        ? '카메라 사용 권한을 허용해주세요.' : error.message)
    } finally {
      starting.current = false
    }
  }

  async function submit(e) {
    e.preventDefault()
    if (!ready || busy) return
    setBusy(true)
    setMessage('')
    try {
      const source = video.current
      if (!source?.videoWidth) throw new Error('카메라가 준비될 때까지 기다려주세요.')
      const canvas = document.createElement('canvas')
      canvas.width = source.videoWidth
      canvas.height = source.videoHeight
      canvas.getContext('2d').drawImage(source, 0, 0)
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9))
      if (!blob) throw new Error('촬영에 실패했습니다. 다시 시도해주세요.')
      const data = new FormData()
      data.append('photo', blob, 'webcam.jpg')
      if (me) data.append('password', password)
      const result = await api.post(me ? '/api/faceauth/register' : '/api/faceauth/login', data)
      stop()
      setMessage(result.message)
      setPassword('')
      await refresh()
      if (!me) navigate('/')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (me?.face_user_id) {
    return (
      <div className="narrow" style={{ maxWidth: 560, paddingTop: 32 }}>
        <h1>내 얼굴 등록 정보</h1>
        <div role="status" style={{ marginTop: 20, padding: 24, borderRadius: 12, background: '#163526', color: '#d1fae5', border: '1px solid #34865c' }}>
          <strong style={{ fontSize: 20 }}>✓ 얼굴 등록 완료</strong>
          <p style={{ marginBottom: 0 }}>{me.name || me.id} 계정에 얼굴이 등록되어 있습니다.</p>
        </div>
        <p>다음 로그인부터 페이스 로그인을 사용할 수 있어요.</p>
        <Link to="/">홈으로 돌아가기</Link>
      </div>
    )
  }

  return (
    <div className="narrow" style={{ maxWidth: 440, paddingTop: 40 }}>
      <Card>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <span className="logo" style={{ justifyContent: 'center', marginLeft: 0 }}>
            <span className="logo-mark"><Ic.Play size={16} /></span>TubeLite
          </span>
          <h1 style={{ marginTop: 16, fontSize: 24, fontWeight: 400 }}>
            {me ? '얼굴 등록' : '로그인'}
          </h1>
          <div className="muted" style={{ fontSize: 14 }}>
            {me ? `${me.name || me.id} 계정에 얼굴 등록` : 'TubeLite로 이동'}
          </div>
        </div>
        {!me && <div className="row" style={{ gap: 12, marginBottom: 20 }}>
          <Link to="/login" style={{ color: 'var(--blue)' }}>비밀번호로 로그인하기</Link>
          <span style={{ fontWeight: 600 }}>페이스 로그인하기</span>
        </div>}
        <div style={{ position: 'relative', aspectRatio: '4 / 3', background: '#181818', border: '1px solid #444', borderRadius: 12, overflow: 'hidden' }}>
          <video ref={video} autoPlay playsInline muted
            style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', visibility: ready ? 'visible' : 'hidden' }} />
          {!ready && <div role="status" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', padding: 24, textAlign: 'center', color: '#ddd' }}>
            {paused ? '카메라 사용을 종료했습니다.' : message ? '카메라 연결을 확인해주세요.' : '카메라 연결 중… 사용 권한을 허용해주세요.'}
          </div>}
          {ready && <div aria-hidden="true" style={{ position: 'absolute', inset: '12% 22%', border: '2px solid rgba(255,255,255,.7)', borderRadius: '50%', pointerEvents: 'none' }} />}
        </div>
        <p className="muted" style={{ fontSize: 13, textAlign: 'center', margin: '12px 0 20px' }}>얼굴을 화면 중앙에 맞춰주세요.</p>
        <form onSubmit={submit} className="form">
          {me && <Field label="현재 계정 비밀번호">
            <input type="password" autoComplete="current-password" required
              value={password} onChange={e => setPassword(e.target.value)} />
          </Field>}
          <div className="row between" style={{ gap: 12 }}>
            {ready ? <Button type="button" variant="ghost" onClick={() => { stop(); setPaused(true) }} disabled={busy}>카메라 종료</Button>
              : <Button type="button" variant="ghost" onClick={start} disabled={busy || (!message && !paused)}>다시 연결</Button>}
            <Button type="submit" variant="accent" disabled={!ready || busy}>
              {busy ? '확인 중…' : me ? '촬영하고 얼굴 등록' : '촬영하고 로그인'}
            </Button>
          </div>
          {message && <p role="status" style={{ margin: 0 }}>{message}</p>}
          <p className="muted" style={{ fontSize: 12, marginTop: 16 }}>
            촬영한 사진 한 장을 AWS에 전송해 얼굴을 비교합니다.
            {!me && ' 등록된 얼굴 정보가 없다면 비밀번호로 로그인한 후 얼굴을 등록해주세요.'}
          </p>
        </form>
      </Card>
    </div>
  )
}
