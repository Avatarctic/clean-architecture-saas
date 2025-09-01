FROM golang:1.21.6-alpine3.19 AS builder

WORKDIR /app

# Update and upgrade system packages to reduce vulnerabilities
RUN apk update && apk upgrade --no-cache && apk add --no-cache git

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o bin/server ./cmd/server

# Final stage
FROM alpine:3.19

# Install ca-certificates for HTTPS requests
RUN apk --no-cache add ca-certificates

# Use a simple working directory
WORKDIR /app

# Copy the binary from builder stage
COPY --from=builder /app/bin/server ./bin/server
COPY --from=builder /app/migrations ./migrations
COPY --from=builder /app/.env.example ./.env.example

# Expose port
EXPOSE 8080

# Run the binary
CMD ["./bin/server"]
