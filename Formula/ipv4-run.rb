class Ipv4Run < Formula
  desc "Run gcloud with IPv4-only Python networking without changing OS settings"
  homepage "https://github.com/s4na/ipv4-run"
  head "https://github.com/s4na/ipv4-run.git", branch: "main"

  depends_on "python@3.14"

  def install
    libexec.install "bin", "libexec"
    inreplace libexec/"bin/ipv4-run", "#!/usr/bin/env python3",
              "#!#{Formula["python@3.14"].opt_bin}/python3.14"
    bin.install_symlink libexec/"bin/ipv4-run"
  end

  test do
    assert_match "gcloud", shell_output("#{bin}/ipv4-run --help")
    assert_match "only gcloud is supported", shell_output("#{bin}/ipv4-run sh 2>&1", 2)
  end
end
