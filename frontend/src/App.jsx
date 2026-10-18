import React, { useState, useEffect } from 'react';
import {
  User as UserIcon,
  Lock,
  Mail,
  Download,
  AlertCircle,
  Loader2,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('smartcut_token') || '');
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login');

  const [nama, setNama] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authMessage, setAuthMessage] = useState({ type: '', text: '' });

  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [validatingUrl, setValidatingUrl] = useState(false);
  const [videoMeta, setVideoMeta] = useState(null);
  const [urlError, setUrlError] = useState('');

  const [addSubtitle, setAddSubtitle] = useState(true);
  const [translateId, setTranslateId] = useState(false);

  const [processingClip, setProcessingClip] = useState(false);
  const [activeClip, setActiveClip] = useState(null);
  const [myClips, setMyClips] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [toast, setToast] = useState('');

  const showNotification = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3500);
  };

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
      fetchMyClips();
    }
  }, [token]);

  useEffect(() => {
    if (!activeClip || activeClip.status_process !== 'Processing') return;

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/videos/${activeClip.clip_id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setActiveClip(data);
          if (data.status_process !== 'Processing') {
            setProcessingClip(false);
            fetchCurrentUser();
            fetchMyClips();
            if (data.status_process === 'Completed') {
              showNotification('Klip video selesai diproses.');
            }
          }
        }
      } catch (err) {
        console.error(err);
      }
    }, 1500);

    return () => clearInterval(timer);
  }, [activeClip, token]);

  const fetchCurrentUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        handleLogout();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMyClips = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/videos/my-clips`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMyClips(data);
        if (!activeClip && data.length > 0) {
          setActiveClip(data[0]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthMessage({ type: '', text: '' });

    const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
    const payload =
      authMode === 'register' ? { nama, email, password } : { email, password };

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        setAuthMessage({ type: 'error', text: data.detail || 'Terjadi kesalahan.' });
      } else {
        localStorage.setItem('smartcut_token', data.access_token);
        setToken(data.access_token);
        setUser(data.user);
      }
    } catch (err) {
      setAuthMessage({
        type: 'error',
        text: 'Tidak dapat terhubung ke server backend (port 8000).',
      });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('smartcut_token');
    setToken('');
    setUser(null);
    setVideoMeta(null);
    setActiveClip(null);
    setMyClips([]);
  };

  const handleUrlChange = async (val) => {
    setYoutubeUrl(val);
    setUrlError('');
    if (!val.trim()) {
      setVideoMeta(null);
      return;
    }

    setValidatingUrl(true);
    try {
      const res = await fetch(`${API_BASE}/api/videos/validate-url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ youtube_url: val }),
      });
      const data = await res.json();
      if (!res.ok) {
        setVideoMeta(null);
        setUrlError(data.detail || 'URL tidak valid.');
      } else {
        setVideoMeta(data);
        setUrlError('');
      }
    } catch (err) {
      setUrlError('Gagal memeriksa URL.');
    } finally {
      setValidatingUrl(false);
    }
  };

  const handleCreateClip = async () => {
    if (!youtubeUrl.trim()) {
      setUrlError('Masukkan URL YouTube terlebih dahulu.');
      return;
    }

    if (user?.account_status === 'Free' && user?.sisa_kuota <= 0) {
      setShowUpgradeModal(true);
      return;
    }

    setProcessingClip(true);
    setUrlError('');
    try {
      const res = await fetch(`${API_BASE}/api/videos/create-clip`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          youtube_url: youtubeUrl,
          add_subtitle: addSubtitle,
          translate_id: translateId,
        }),
      });
      const data = await res.json();
      if (res.status === 402) {
        setProcessingClip(false);
        setShowUpgradeModal(true);
        return;
      }
      if (!res.ok) {
        setProcessingClip(false);
        setUrlError(data.detail || 'Gagal memproses video.');
        return;
      }

      setActiveClip(data);
      fetchCurrentUser();
      fetchMyClips();
    } catch (err) {
      setProcessingClip(false);
      setUrlError('Gagal menghubungi server.');
    }
  };

  const handleSimulateUpgrade = async () => {
    setUpgrading(true);
    try {
      const res = await fetch(`${API_BASE}/api/transactions/simulate-upgrade`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        setShowUpgradeModal(false);
        fetchCurrentUser();
        showNotification(`Akun berhasil di-upgrade ke Premium (${data.order_id})`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setUpgrading(false);
    }
  };

  const formatCleanTranscript = (rawText) => {
    if (!rawText) return 'Transkrip segmen belum tersedia.';
    const lines = rawText
      .split('\n')
      .filter(
        (line) =>
          !line.trim().startsWith('[') &&
          !line.trim().startsWith('Selected Highlight:') &&
          !line.trim().startsWith('Segmen Terpilih:')
      );
    const cleaned = lines.join(' ').replace(/^"|"$/g, '').trim();
    return cleaned || rawText;
  };

  if (!token || !user) {
    return (
      <div className="min-h-screen w-full flex flex-col justify-center items-center px-4 bg-[#00382d]">
        <div className="w-full max-w-[380px] bg-white rounded-2xl px-8 py-10 shadow-xl">
          <div className="text-center mb-7">
            <h1 className="text-3xl font-bold text-[#004D3E]">
              {authMode === 'login' ? 'Login' : 'Register'}
            </h1>
            <p className="text-xs text-gray-500 mt-1.5">
              {authMode === 'login'
                ? 'Sign in to your account'
                : 'Create your Web SmartCut account'}
            </p>
          </div>

          {authMessage.text && (
            <div
              className={`mb-4 p-3 rounded-lg text-xs flex items-center gap-2 border ${
                authMessage.type === 'error'
                  ? 'bg-red-50 border-red-200 text-red-600'
                  : 'bg-teal-50 border-teal-200 text-teal-800'
              }`}
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{authMessage.text}</span>
            </div>
          )}

          <form onSubmit={handleAuthSubmit} className="space-y-3">
            {authMode === 'register' && (
              <div className="flex items-center bg-[#eef4f2] rounded-lg px-3.5 py-2.5">
                <UserIcon className="w-4 h-4 text-[#004D3E] mr-3 shrink-0" />
                <input
                  type="text"
                  required
                  placeholder="Nama Lengkap"
                  value={nama}
                  onChange={(e) => setNama(e.target.value)}
                  className="w-full bg-transparent text-xs text-gray-800 placeholder-gray-500 outline-none"
                />
              </div>
            )}

            <div className="flex items-center bg-[#eef4f2] rounded-lg px-3.5 py-2.5">
              {authMode === 'login' ? (
                <UserIcon className="w-4 h-4 text-[#004D3E] mr-3 shrink-0" />
              ) : (
                <Mail className="w-4 h-4 text-[#004D3E] mr-3 shrink-0" />
              )}
              <input
                type="email"
                required
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent text-xs text-gray-800 placeholder-gray-500 outline-none"
              />
            </div>

            <div className="flex items-center bg-[#eef4f2] rounded-lg px-3.5 py-2.5">
              <Lock className="w-4 h-4 text-[#004D3E] mr-3 shrink-0" />
              <input
                type="password"
                required
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-transparent text-xs text-gray-800 placeholder-gray-500 outline-none"
              />
            </div>

            <div className="flex justify-end pt-0.5 pb-1">
              <span className="text-[11px] text-[#004D3E] hover:underline cursor-pointer">
                Forgot password?
              </span>
            </div>

            <button
              type="submit"
              disabled={authLoading}
              className="w-full bg-[#004D3E] hover:bg-[#00382d] text-white font-semibold text-sm py-2.5 rounded-lg transition cursor-pointer"
            >
              {authLoading
                ? 'Loading...'
                : authMode === 'login'
                ? 'Login'
                : 'Register'}
            </button>
          </form>

          <div className="mt-5 text-center text-xs text-gray-600">
            {authMode === 'login' ? (
              <>
                Don&apos;t have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('register');
                    setAuthMessage({ type: '', text: '' });
                  }}
                  className="text-[#004D3E] font-semibold underline cursor-pointer"
                >
                  Register here
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('login');
                    setAuthMessage({ type: '', text: '' });
                  }}
                  className="text-[#004D3E] font-semibold underline cursor-pointer"
                >
                  Login here
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  const isFree = user.account_status === 'Free';

  return (
    <div className="min-h-screen w-full bg-[#004D3E] p-5 md:p-7 flex flex-col gap-5">
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 bg-gray-900 text-white px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium">
          {toast}
        </div>
      )}

      <div className="flex-1 flex flex-col md:flex-row gap-6 items-stretch">
        <aside
          className={`bg-white rounded-[20px] p-6 sm:p-7 flex flex-col justify-between shrink-0 transition-all shadow-md ${
            sidebarOpen ? 'w-full md:w-[280px]' : 'w-full md:w-[84px]'
          }`}
        >
          <div>
            <div className="flex items-center gap-3 min-h-[40px] mb-5">
              <button
                type="button"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition cursor-pointer"
              >
                <div className="space-y-1">
                  <span className="block w-4 h-0.5 bg-black"></span>
                  <span className="block w-4 h-0.5 bg-black"></span>
                  <span className="block w-4 h-0.5 bg-black"></span>
                </div>
              </button>
              {sidebarOpen && (
                <span className="text-xl font-extrabold text-black tracking-tight">
                  Web SmartCut
                </span>
              )}
            </div>

            {sidebarOpen && (
              <>
                <div className="w-full bg-black text-white font-madimi text-sm py-3.5 px-5 rounded-full text-center mb-4">
                  Riwayat Klip
                </div>

                <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                  {myClips.length === 0 ? (
                    <p className="text-xs text-gray-400 text-center py-6">
                      Belum ada klip.
                    </p>
                  ) : (
                    myClips.map((clip) => {
                      const isSelected = activeClip?.clip_id === clip.clip_id;
                      return (
                        <div
                          key={clip.clip_id}
                          onClick={() => setActiveClip(clip)}
                          className={`p-2.5 rounded-xl cursor-pointer transition flex items-center gap-2.5 ${
                            isSelected
                              ? 'bg-[#004D3E] text-white'
                              : 'hover:bg-gray-100 text-gray-800'
                          }`}
                        >
                          {clip.thumbnail_url && (
                            <img
                              src={clip.thumbnail_url}
                              alt=""
                              className="w-11 h-8 object-cover rounded shrink-0 bg-gray-200"
                            />
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold truncate">
                              {clip.video_title}
                            </p>
                            <p
                              className={`text-[10px] mt-0.5 ${
                                isSelected ? 'text-[#B2DFDB]' : 'text-gray-400'
                              }`}
                            >
                              {clip.segment_timestamp}
                            </p>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            )}
          </div>

          <div className="pt-4 mt-4 border-t border-gray-100">
            {sidebarOpen && (
              <div className="mb-3 px-1">
                <p className="text-xs font-bold text-gray-800 truncate">{user.nama}</p>
                <p className="text-[11px] text-gray-400 truncate">{user.email}</p>
              </div>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="w-full bg-black hover:bg-gray-800 text-white font-madimi text-sm py-3 px-4 rounded-full text-center transition cursor-pointer"
            >
              {sidebarOpen ? 'LOGOUT' : '⏻'}
            </button>
          </div>
        </aside>

        <div className="flex-1 flex flex-col gap-6 min-w-0">
          <div className="bg-white rounded-[20px] p-6 sm:p-7 shadow-md flex flex-col justify-between">
            <div>
              <div className="flex flex-wrap items-center justify-between gap-3 min-h-[40px] mb-5">
                <label className="font-madimi text-xl sm:text-2xl text-black">
                  Masukkan URL Youtube Disini
                </label>

                <div
                  onClick={() => isFree && setShowUpgradeModal(true)}
                  className={`bg-[#B2DFDB] px-4 py-1.5 rounded-full flex items-center gap-2.5 ${
                    isFree ? 'cursor-pointer hover:brightness-95 transition' : ''
                  }`}
                >
                  <span className="font-bold text-black text-xs sm:text-sm">
                    Status Akun : {isFree ? `Free (${user.sisa_kuota}/2)` : 'Premium'}
                  </span>
                  {isFree && (
                    <span className="bg-[#004D3E] text-white text-[11px] font-semibold px-2.5 py-0.5 rounded-full">
                      Upgrade
                    </span>
                  )}
                </div>
              </div>

              <div className="relative">
                <input
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => handleUrlChange(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full bg-[#004D3E] text-white placeholder-white/60 rounded-full px-5 py-3.5 text-sm outline-none"
                />
                {validatingUrl && (
                  <div className="absolute right-4 top-3.5 text-xs text-[#B2DFDB]">
                    Memuat info...
                  </div>
                )}
              </div>

              {urlError && (
                <p className="mt-2 text-xs text-red-600 font-medium">{urlError}</p>
              )}

              {videoMeta && (
                <div className="mt-3.5 flex items-center gap-3.5 p-3 rounded-xl bg-gray-50 border border-gray-200">
                  <img
                    src={videoMeta.thumbnail_url}
                    alt=""
                    className="w-24 h-14 object-cover rounded-lg shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold text-gray-900 truncate">
                      {videoMeta.video_title}
                    </p>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      {videoMeta.channel_name} • Durasi: {videoMeta.duration_formatted}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mt-4">
                <div
                  onClick={() => (isFree ? setShowUpgradeModal(true) : setAddSubtitle(!addSubtitle))}
                  className="bg-[#004D3E] rounded-[22px] px-5 py-3.5 flex items-center justify-between cursor-pointer select-none"
                >
                  <span className="font-madimi text-lg text-white">Auto Subtitle</span>
                  <div className="w-8 h-8 bg-white rounded flex items-center justify-center text-black font-bold text-lg">
                    {!isFree && addSubtitle ? '✓' : ''}
                  </div>
                </div>

                <div
                  onClick={() => (isFree ? setShowUpgradeModal(true) : setTranslateId(!translateId))}
                  className="bg-[#004D3E] rounded-[22px] px-5 py-3.5 flex items-center justify-between cursor-pointer select-none"
                >
                  <span className="font-madimi text-lg text-white">
                    Terjemahkan ke Indonesia
                  </span>
                  <div className="w-8 h-8 bg-white rounded flex items-center justify-center text-black font-bold text-lg">
                    {!isFree && translateId ? '✓' : ''}
                  </div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleCreateClip}
              disabled={processingClip}
              className="mt-4 w-full bg-[#004D3E] hover:bg-[#003b30] disabled:opacity-60 text-white font-madimi text-xl py-3.5 rounded-[22px] transition cursor-pointer"
            >
              {processingClip ? 'Sedang Memproses Klip...' : 'Buat Klip Sekarang'}
            </button>
          </div>

          {activeClip && (
            <div className="bg-white rounded-[20px] p-6 sm:p-7 shadow-md">
              {activeClip.status_process === 'Processing' ? (
                <div className="py-12 flex flex-col items-center justify-center text-center">
                  <Loader2 className="w-8 h-8 text-[#004D3E] animate-spin mb-3" />
                  <p className="text-sm font-bold text-gray-800">
                    Memotong segmen video & audio...
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Proses ini memerlukan waktu sekitar 15–25 detik.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-7 items-start">
                  <div className="lg:col-span-4 flex flex-col items-center">
                    <div className="relative aspect-[9/16] w-full max-w-[230px] bg-black rounded-xl overflow-hidden border border-gray-200">
                      {activeClip.download_url && (
                        <video
                          key={`${activeClip.clip_id}-${activeClip.file_path}`}
                          src={`${API_BASE}${activeClip.download_url}?v=${encodeURIComponent(
                            activeClip.file_path || activeClip.clip_id
                          )}`}
                          controls
                          autoPlay
                          playsInline
                          className="w-full h-full object-cover bg-black"
                        />
                      )}

                      {activeClip.has_watermark === 1 && (
                        <div className="absolute top-2.5 left-2.5 right-2.5 pointer-events-none bg-black/65 text-white px-2 py-1 rounded text-[10px] font-semibold text-center">
                          SmartCut Free
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="lg:col-span-8 flex flex-col justify-between h-full">
                    <div>
                      <div className="pb-4 border-b border-gray-100">
                        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                          Hasil Potongan Klip
                        </span>
                        <h3 className="text-lg font-bold text-gray-900 mt-0.5 leading-snug">
                          {activeClip.video_title}
                        </h3>
                      </div>

                      <div className="grid grid-cols-3 gap-3 py-4 border-b border-gray-100">
                        <div>
                          <p className="text-[11px] text-gray-400">Rentang Waktu</p>
                          <p className="text-xs font-bold text-gray-800 mt-0.5">
                            {activeClip.segment_timestamp}
                          </p>
                        </div>
                        <div>
                          <p className="text-[11px] text-gray-400">Format Rasio</p>
                          <p className="text-xs font-bold text-gray-800 mt-0.5">
                            9:16 Vertikal (MP4)
                          </p>
                        </div>
                        <div>
                          <p className="text-[11px] text-gray-400">Watermark</p>
                          <p className="text-xs font-bold text-gray-800 mt-0.5">
                            {activeClip.has_watermark ? 'Aktif (Free)' : 'Tanpa Watermark'}
                          </p>
                        </div>
                      </div>

                      <div className="py-4 border-b border-gray-100">
                        <p className="text-xs font-semibold text-gray-700 mb-1.5">
                          Catatan Transkrip Segmen
                        </p>
                        <p className="text-xs text-gray-600 leading-relaxed bg-gray-50 p-3.5 rounded-lg border border-gray-100">
                          {formatCleanTranscript(activeClip.transcript_text)}
                        </p>
                      </div>

                      {activeClip.logs && activeClip.logs.length > 0 && (
                        <div className="py-4">
                          <p className="text-xs font-semibold text-gray-700 mb-2">
                            Status Proses Server
                          </p>
                          <div className="border border-gray-100 rounded-lg divide-y divide-gray-100 text-xs">
                            {activeClip.logs.map((lg) => (
                              <div
                                key={lg.log_id}
                                className="flex items-center justify-between px-3.5 py-2"
                              >
                                <span className="text-gray-600">{lg.process_type}</span>
                                <span className="text-gray-400 font-medium">
                                  {(lg.execution_time_ms / 1000).toFixed(1)} dtk
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {activeClip.download_url && (
                      <div className="pt-2">
                        <a
                          href={`${API_BASE}${activeClip.download_url}`}
                          download={`SmartCut_Clip_${activeClip.clip_id}.mp4`}
                          className="inline-flex items-center justify-center gap-2 bg-[#004D3E] hover:bg-[#00382d] text-white font-semibold text-xs px-6 py-3 rounded-lg transition"
                        >
                          <Download className="w-4 h-4" />
                          <span>Unduh File MP4</span>
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showUpgradeModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Upgrade ke Premium</h3>
            <p className="text-xs text-gray-500 mt-1">
              Dapatkan akses penuh tanpa batas kuota bulanan.
            </p>

            <div className="my-5 p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2 text-xs">
              <div className="flex justify-between font-bold text-gray-900 pb-2 border-b border-gray-200">
                <span>Paket Bulanan</span>
                <span>Rp 39.000</span>
              </div>
              <p className="text-gray-600 pt-1">• Pembuatan klip tanpa batas kuota</p>
              <p className="text-gray-600">• Hasil video bersih tanpa watermark</p>
              <p className="text-gray-600">• Fitur Auto Subtitle & Terjemahan</p>
            </div>

            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={() => setShowUpgradeModal(false)}
                className="flex-1 py-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleSimulateUpgrade}
                disabled={upgrading}
                className="flex-1 py-2.5 rounded-lg bg-[#004D3E] hover:bg-[#00382d] text-white text-xs font-semibold cursor-pointer"
              >
                {upgrading ? 'Memproses...' : 'Bayar Sekarang'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
