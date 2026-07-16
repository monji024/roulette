#!/usr/bin/env ruby

require 'pathname'

Encoding.default_external = Encoding::UTF_8
Encoding.default_internal = Encoding::UTF_8

ASSET_PATH = Pathname.new(__dir__).join('..', 'assets', 'texts.txt')
HISTORY_PATH = Pathname.new(__dir__).join('..', 'data', '.texts_history')

def load_pool(path)
  unless path.exist?
    warn "texts.rb: asset file not found at #{path}"
    exit 2
  end
  pool = Hash.new { |h, k| h[k] = [] }
  current_category = nil
  path.read(encoding: 'UTF-8').each_line do |raw_line|
    line = raw_line.strip
    next if line.empty?
    next if line.start_with?('#')
    if line =~ /^\[([A-Z_]+)\]$/
      current_category = Regexp.last_match(1)
      next
    end
    pool[current_category] << line if current_category
  end
  pool
end

def pick_line(lines, category)
  return nil if lines.nil? || lines.empty?
  return lines.sample if lines.length == 1
  last_choice = nil
  if HISTORY_PATH.exist?
    File.foreach(HISTORY_PATH) do |entry|
      key, value = entry.strip.split('=', 2)
      last_choice = value if key == category
    end
  end
  candidates = lines.reject { |l| l == last_choice }
  candidates = lines if candidates.empty?
  choice = candidates.sample
  begin
    history = {}
    if HISTORY_PATH.exist?
      File.foreach(HISTORY_PATH) do |entry|
        key, value = entry.strip.split('=', 2)
        history[key] = value if key
      end
    end
    history[category] = choice
    HISTORY_PATH.dirname.mkpath
    File.write(HISTORY_PATH, history.map { |k, v| "#{k}=#{v}" }.join("\n"))
  rescue StandardError
  end
  choice
end

def main
  category = ARGV[0]
  if category.nil? || category.strip.empty?
    warn 'texts.rb: usage: ruby texts.rb <CATEGORY>'
    exit 1
  end
  category = category.strip.upcase
  pool = load_pool(ASSET_PATH)
  unless pool.key?(category)
    warn "texts.rb: unknown category '#{category}'"
    exit 1
  end
  line = pick_line(pool[category], category)
  puts line
end

main if __FILE__ == $PROGRAM_NAME
