#ifndef __COUNTS_PER_MINUTE_H__
#define __COUNTS_PER_MINUTE_H__

class CountsPerMinute {
  int m_currentCpm;
  int m_maximumCpm;
  int m_intervalsPerMinute;
  int * m_intervalCounts;
  int m_currentInterval;
  int m_initialInterval;

  public:

    CountsPerMinute() {}

  void init(int intervalsPerMinute) {
    this -> m_currentCpm = 0;
    this -> m_maximumCpm = 0;
    this -> m_intervalsPerMinute = intervalsPerMinute;
    this -> m_intervalCounts = new int[this -> m_intervalsPerMinute];
    for (int i = 0; i < this -> m_intervalsPerMinute; i++) {
      this -> m_intervalCounts[i] = 0;
    }
    this -> m_currentInterval = 0;
    this -> m_initialInterval = 0;
  }

  bool isReady() {
    return this -> m_initialInterval >= this -> m_intervalsPerMinute;
  }

  int getCurrentCpm() {
    return this -> m_currentCpm;
  }

  int getMaximumCpm() {
    return this -> m_maximumCpm;
  }

  void add(int count) {
    if (this -> isReady()) {
      this -> m_currentCpm = this -> m_currentCpm - this -> m_intervalCounts[m_currentInterval] + count;
    } else {
      this -> m_currentCpm += count;
      this -> m_initialInterval++;
    }

    if (this -> m_maximumCpm < this -> m_currentCpm) {
      this -> m_maximumCpm = this -> m_currentCpm;
    }

    this -> m_intervalCounts[m_currentInterval] = count;

    m_currentInterval++;
    if (m_currentInterval >= m_intervalsPerMinute) {
      m_currentInterval = 0;
    }
  }

};

#endif // __COUNTS_PER_MINUTE_H__
