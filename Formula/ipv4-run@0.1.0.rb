require "shellwords"

class Ipv4RunAT010 < Formula
  desc "Run gcloud with IPv4-only Python networking without changing OS settings"
  homepage "https://github.com/s4na/ipv4-run"
  url "https://github.com/s4na/ipv4-run/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "1cfb80f735b81a750c9503eae26b97fb782e8af1a3ab9f1124ae5674fff0085b"

  keg_only :versioned_formula

  depends_on "python@3.14"

  def install
    libexec.install "bin", "libexec"
    launcher = (libexec/"libexec/ipv4-run-homebrew.sh").read
    launcher = launcher.gsub("@FALLBACK_PYTHON@") { (Formula["python@3.14"].opt_bin/"python3.14").to_s.shellescape }
    launcher = launcher.gsub("@CLI@") { (libexec/"bin/ipv4-run").to_s.shellescape }
    bin.mkpath
    (bin/"ipv4-run").write launcher
    (bin/"ipv4-run").chmod 0755
  end

  test do
    assert_match "gcloud", shell_output("#{bin}/ipv4-run --help")
    assert_match "only gcloud is supported", shell_output("#{bin}/ipv4-run sh 2>&1", 2)
  end
end
