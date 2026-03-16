/*
 * iBroadcast Album Art Visualizer for Kodi
 *
 * Renders the currently playing track's album art full-screen using OpenGL.
 * Artwork is fetched via Kodi's VFS (handles local cache paths and HTTP URLs).
 */

#include <kodi/addon-instance/Visualization.h>
#include <kodi/Filesystem.h>
#include <kodi/General.h>
#include <kodi/gui/gl/GL.h>

#define STB_IMAGE_IMPLEMENTATION
#define STBI_NO_STDIO
#include "stb_image.h"

#include <string>
#include <vector>
#include <cstring>

// ── GLSL shaders ──────────────────────────────────────────────────────────────

static const char* VERT_SRC =
#if defined(HAS_GLES)
  "precision mediump float;\n"
  "attribute vec2 a_pos;\n"
  "attribute vec2 a_uv;\n"
  "varying   vec2 v_uv;\n"
#else
  "#version 150\n"
  "in  vec2 a_pos;\n"
  "in  vec2 a_uv;\n"
  "out vec2 v_uv;\n"
#endif
  "void main() {\n"
  "  v_uv        = a_uv;\n"
  "  gl_Position = vec4(a_pos, 0.0, 1.0);\n"
  "}\n";

static const char* FRAG_SRC =
#if defined(HAS_GLES)
  "precision mediump float;\n"
  "varying   vec2      v_uv;\n"
  "uniform   sampler2D u_tex;\n"
  "uniform   float     u_alpha;\n"
  "void main() {\n"
  "  gl_FragColor = texture2D(u_tex, v_uv) * vec4(1.0, 1.0, 1.0, u_alpha);\n"
  "}\n";
#else
  "#version 150\n"
  "in      vec2      v_uv;\n"
  "out     vec4      fragColor;\n"
  "uniform sampler2D u_tex;\n"
  "uniform float     u_alpha;\n"
  "void main() {\n"
  "  fragColor = texture(u_tex, v_uv) * vec4(1.0, 1.0, 1.0, u_alpha);\n"
  "}\n";
#endif

// ── Visualizer ────────────────────────────────────────────────────────────────

class CVisualizationAlbumArt
    : public kodi::addon::CAddonBase
    , public kodi::addon::CInstanceVisualization
{
public:
  CVisualizationAlbumArt() = default;

  ~CVisualizationAlbumArt() override
  {
    DeinitGL();
  }

  // Called once when the addon is loaded
  ADDON_STATUS Create() override
  {
    return ADDON_STATUS_OK;
  }

  // Called when playback starts
  bool Start(int channels, int samplesPerSec, int bitsPerSample,
             const std::string& songName) override
  {
    if (!m_glReady)
      InitGL();
    m_currentArt.clear();   // force art reload on next Render()
    return true;
  }

  void Stop() override {}

  void AudioData(const float* audioData, size_t audioDataLength) override {}

  bool IsDirty() override { return true; }

  void Render() override
  {
    if (!m_glReady)
      return;

    // Reload art if the track has changed
    std::string thumb = kodi::GetInfoLabel("Player.Art(thumb)");
    if (thumb != m_currentArt)
    {
      m_currentArt = thumb;
      LoadTexture(thumb);
    }

    // Black background
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    if (!m_texture || m_texW == 0 || m_texH == 0)
      return;

    // Recompute the centred quad if the viewport changed
    int vw = Width(), vh = Height();
    if (vw != m_viewW || vh != m_viewH)
      RebuildQuad(vw, vh);

    glUseProgram(m_program);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, m_texture);
    glUniform1i(m_locTex,   0);
    glUniform1f(m_locAlpha, 1.0f);

    glBindVertexArray(m_vao);
    glDrawArrays(GL_TRIANGLE_FAN, 0, 4);
    glBindVertexArray(0);

    glBindTexture(GL_TEXTURE_2D, 0);
    glUseProgram(0);
  }

private:
  // ── OpenGL init / teardown ─────────────────────────────────────────────────

  GLuint CompileShader(GLenum type, const char* src)
  {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok)
    {
      char log[512] = {};
      glGetShaderInfoLog(s, sizeof(log), nullptr, log);
      kodi::Log(ADDON_LOG_ERROR, "[AlbumArt] shader compile: %s", log);
      glDeleteShader(s);
      return 0;
    }
    return s;
  }

  bool InitGL()
  {
    GLuint vs = CompileShader(GL_VERTEX_SHADER,   VERT_SRC);
    GLuint fs = CompileShader(GL_FRAGMENT_SHADER, FRAG_SRC);
    if (!vs || !fs)
      return false;

    m_program = glCreateProgram();
    glAttachShader(m_program, vs);
    glAttachShader(m_program, fs);
    glBindAttribLocation(m_program, 0, "a_pos");
    glBindAttribLocation(m_program, 1, "a_uv");
    glLinkProgram(m_program);
    glDeleteShader(vs);
    glDeleteShader(fs);

    GLint ok = 0;
    glGetProgramiv(m_program, GL_LINK_STATUS, &ok);
    if (!ok)
    {
      kodi::Log(ADDON_LOG_ERROR, "[AlbumArt] program link failed");
      return false;
    }
    m_locTex   = glGetUniformLocation(m_program, "u_tex");
    m_locAlpha = glGetUniformLocation(m_program, "u_alpha");

    // VAO + VBO (4 verts × { x, y, u, v })
    glGenVertexArrays(1, &m_vao);
    glGenBuffers(1, &m_vbo);
    glBindVertexArray(m_vao);
    glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(m_quad), nullptr, GL_DYNAMIC_DRAW);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float),
                          (void*)(2 * sizeof(float)));
    glEnableVertexAttribArray(1);
    glBindVertexArray(0);

    m_glReady = true;
    return true;
  }

  void DeinitGL()
  {
    DeleteTexture();
    if (m_vbo)     { glDeleteBuffers(1, &m_vbo);      m_vbo = 0; }
    if (m_vao)     { glDeleteVertexArrays(1, &m_vao); m_vao = 0; }
    if (m_program) { glDeleteProgram(m_program);       m_program = 0; }
    m_glReady = false;
  }

  // ── Texture loading ────────────────────────────────────────────────────────

  bool LoadTexture(const std::string& path)
  {
    DeleteTexture();
    if (path.empty())
      return false;

    // Read through Kodi VFS — handles special://, http://, and plain paths
    kodi::vfs::CFile file;
    std::string resolved = kodi::vfs::TranslatePath(path);
    if (!file.OpenFile(resolved.empty() ? path : resolved, 0))
    {
      kodi::Log(ADDON_LOG_WARNING, "[AlbumArt] cannot open: %s", path.c_str());
      return false;
    }

    std::vector<uint8_t> buf;
    buf.reserve(512 * 1024);
    uint8_t chunk[8192];
    ssize_t n;
    while ((n = file.Read(chunk, sizeof(chunk))) > 0)
      buf.insert(buf.end(), chunk, chunk + n);
    file.Close();

    if (buf.empty())
      return false;

    int w, h, comp;
    stbi_set_flip_vertically_on_load(true);   // match OpenGL UV origin
    unsigned char* data =
        stbi_load_from_memory(buf.data(), (int)buf.size(), &w, &h, &comp, 4);
    if (!data)
    {
      kodi::Log(ADDON_LOG_WARNING, "[AlbumArt] stbi decode failed: %s", path.c_str());
      return false;
    }

    glGenTextures(1, &m_texture);
    glBindTexture(GL_TEXTURE_2D, m_texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, data);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glBindTexture(GL_TEXTURE_2D, 0);

    stbi_image_free(data);
    m_texW  = w;
    m_texH  = h;
    m_viewW = 0;   // force quad recalc
    kodi::Log(ADDON_LOG_INFO, "[AlbumArt] loaded %dx%d from %s", w, h, path.c_str());
    return true;
  }

  void DeleteTexture()
  {
    if (m_texture) { glDeleteTextures(1, &m_texture); m_texture = 0; }
    m_texW = m_texH = 0;
  }

  // ── Quad geometry (centred, aspect-ratio correct) ─────────────────────────

  void RebuildQuad(int vw, int vh)
  {
    m_viewW = vw;
    m_viewH = vh;

    float artAR  = (float)m_texW / (float)m_texH;
    float viewAR = (float)vw     / (float)vh;

    float x0, y0, x1, y1;
    if (artAR > viewAR)
    {
      // Letterbox — bars top and bottom
      float h = viewAR / artAR;
      x0 = -1.0f; x1 =  1.0f;
      y0 = -h;    y1 =  h;
    }
    else
    {
      // Pillarbox — bars left and right
      float w = artAR / viewAR;
      x0 = -w;    x1 =  w;
      y0 = -1.0f; y1 =  1.0f;
    }

    // Triangle fan: BL → BR → TR → TL  (each: x, y, u, v)
    m_quad[ 0] = x0; m_quad[ 1] = y0; m_quad[ 2] = 0.0f; m_quad[ 3] = 0.0f;
    m_quad[ 4] = x1; m_quad[ 5] = y0; m_quad[ 6] = 1.0f; m_quad[ 7] = 0.0f;
    m_quad[ 8] = x1; m_quad[ 9] = y1; m_quad[10] = 1.0f; m_quad[11] = 1.0f;
    m_quad[12] = x0; m_quad[13] = y1; m_quad[14] = 0.0f; m_quad[15] = 1.0f;

    glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(m_quad), m_quad);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
  }

  // ── State ──────────────────────────────────────────────────────────────────

  bool    m_glReady  = false;
  GLuint  m_program  = 0;
  GLuint  m_vao      = 0;
  GLuint  m_vbo      = 0;
  GLuint  m_texture  = 0;
  GLint   m_locTex   = -1;
  GLint   m_locAlpha = -1;
  int     m_texW = 0, m_texH = 0;
  int     m_viewW = 0, m_viewH = 0;
  float   m_quad[16] = {};
  std::string m_currentArt;
};

ADDONCREATOR(CVisualizationAlbumArt)
