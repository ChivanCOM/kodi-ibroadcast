cmake_minimum_required(VERSION 3.10)
project(visualization.ibroadcast.albumart)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Kodi dev-kit headers ──────────────────────────────────────────────────────
if(NOT DEFINED KODI_INCLUDE_DIR)
  set(KODI_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/kodi-dev-kit/include"
      CACHE PATH "Path to Kodi addon dev-kit include directory")
endif()
include_directories(${KODI_INCLUDE_DIR})
include_directories(${CMAKE_SOURCE_DIR}/src)

# ── Platform definitions needed by kodi/gui/gl/GL.h ──────────────────────────
if(APPLE)
  add_definitions(-DHAS_GL=1 -DTARGET_DARWIN -DGL_SILENCE_DEPRECATION)
elseif(UNIX)
  add_definitions(-DHAS_GL=1 -DTARGET_LINUX)
elseif(WIN32)
  add_definitions(-DHAS_GL=1)
endif()

# ── OpenGL ────────────────────────────────────────────────────────────────────
find_package(OpenGL REQUIRED)
include_directories(${OPENGL_INCLUDE_DIR})

# ── Build shared library ──────────────────────────────────────────────────────
add_library(${PROJECT_NAME} MODULE src/main.cpp)

target_link_libraries(${PROJECT_NAME} ${OPENGL_LIBRARIES})

set_target_properties(${PROJECT_NAME} PROPERTIES
  PREFIX ""
  OUTPUT_NAME "${PROJECT_NAME}"
)

if(APPLE)
  set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".dylib")
elseif(UNIX)
  set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".so")
endif()

# ── Install into addon folder ─────────────────────────────────────────────────
install(TARGETS ${PROJECT_NAME}
  LIBRARY DESTINATION "${CMAKE_SOURCE_DIR}/.."
)
install(FILES "${CMAKE_SOURCE_DIR}/../addon.xml"
              "${CMAKE_SOURCE_DIR}/../icon.png"
  DESTINATION "${CMAKE_SOURCE_DIR}/.."
)
