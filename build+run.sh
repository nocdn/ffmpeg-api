docker build -t ffmpeg-api-img .
docker run -d \
      --restart=always \
      -p 8040:8000 \
      --name ffmpeg-api-container \
      ffmpeg-api-img