var QetchQuery = angular.module('QetchQuery');

QetchQuery.service('QetchQuery_QueryAPI', ['$rootScope', 'DatasetAPI', 'Data_Utils', 'Parameters', function ($rootScope, DatasetAPI, Data_Utils, Parameters) {
  var self = this;

  this.points = []; // 查询中提取的所有点
  this.tangents = []; // 查询中所有的切线
  this.sections = []; // 查询中所有的部分
  this.notOperator = -1; // -1 表示 false，任何其他正数表示操作应使用该阈值进行取反
  this.queryLength = null;
  this.queryLengthTolerance = null;
  this.queryHeight = null;
  this.queryHeightTolerance = null;
  this.queryHorizontalOffset = null;
  this.queryVerticalOffset = null;

  this.isEmpty = function () {
    return this.points.length === 0;
  };

  this.clear = function () {
    this.points = [];
    this.tangents = [];
    this.sections = [];
    this.notOperator = -1;
    DatasetAPI.clearMatches();
    $rootScope.$broadcast(Parameters.QUERY_EVENTS.CLEAR);
  };

  this.setPoints = function (points) {
    this.points = points;
    this.tangents = this.extractTangents(points);
    this.sections = this.findCurveSections(this.tangents, points, Parameters.DIVIDE_SECTION_MIN_HEIGHT_QUERY);
    this.findMatches();
  };

  this.findMatches = function () {
    Parameters.LAST_EXECUTION_QUERY_LENGTH = this.queryLength;

    var matches;
    if (Parameters.ALGORITHM_TO_USE == 'dtw' || Parameters.ALGORITHM_TO_USE == 'ed') {
      matches = this.queryLength ? this.executeQueryVDTWorVED() : [];
    } else {
      matches = this.executeQuery();
    }

    DatasetAPI.setMatches(matches);
    DatasetAPI.notifyMatchesChanged();
  };
  
  this.setQueryLength = function (queryLength, tolerance, strictMode) {
    this.queryLength = queryLength;
    this.queryLengthTolerance = tolerance;
    this.queryLengthStrictMode = strictMode;
  };

  this.setQueryHeight = function (queryHeight, tolerance) {
    this.queryHeight = queryHeight;
    this.queryHeightTolerance = tolerance;
  };

  this.setQueryHorizontalOffset = function (queryHorizontalOffset) {
    this.queryHorizontalOffset = queryHorizontalOffset;
  };

  this.setQueryVerticalOffset = function (queryVerticalOffset) {
    this.queryVerticalOffset = queryVerticalOffset;
  };

  /**
   * 执行查询
   * 这只查看平滑。然后启动 executeQueryRec
   * 然后通知结果
   */
  this.executeQuery = function () {
    var startingTime = new Date();

    var queryCtx = {
      matches: [],
      notMatches: [],
      snum: 0,
      smoothi: 0,
      notOperator: this.notOperator,
      notOperatorVal: -1,
      datasetSize: null,
      dataPoints: []
    };

    queryCtx.datasetSize = null;

    for (queryCtx.snum = 0; queryCtx.snum < DatasetAPI.getDatasetsNum(); queryCtx.snum++) {
      var smoothIterationsNum = DatasetAPI.getSmoothIterationsNum(queryCtx.snum);
      if (smoothIterationsNum === 0) throw '没有数据可查询'; // 应由 UI 控制
      for (queryCtx.smoothi = 0; queryCtx.smoothi < smoothIterationsNum; queryCtx.smoothi++) {
        queryCtx.dataPoints = DatasetAPI.getData(queryCtx.snum, queryCtx.smoothi);
        this.executeQueryInSI(queryCtx);
      }
    }

    var finishingTime = new Date();
    Qetch.DEBUG_LAST_EXECUTING_TIME = finishingTime - startingTime;

    return this.notOperator >= 0 ? queryCtx.notMatches : queryCtx.matches;
  };

  /**
   * 在特定的平滑迭代中执行查询
   */
  this.executeQueryInSI = function (queryCtx) {
    var dsi;

    if (queryCtx.datasetSize === null) {
      queryCtx.datasetSize = _.last(queryCtx.dataPoints).x - queryCtx.dataPoints[0].x;
    }
    var dataTangents = this.extractTangents(queryCtx.dataPoints);
    var dataSections = this.findCurveSections(dataTangents, queryCtx.dataPoints, Parameters.DIVIDE_SECTION_MIN_HEIGHT_DATA);

    for (dsi = 0; dsi < dataSections.length; dsi++) {
      for (var i = 0; i < this.sections.length; i++) {
        for (var j = 0; j < this.sections[i].next.length; j++) {
          this.sections[i].next[j].times = 1;
        }
      }
      if (this.matchIn(this.sections[0], dataSections, dsi, [], queryCtx, _.last(this.sections)) === false) break;
    }

    if (this.notOperator >= 0) {
      if (this.notOperator == 0) { // 自动计算值
        var avgMatchValue = 0, avgMatchValueCount = 0;
        for (var i = 0; i < queryCtx.matches.length; i++) {
          var mtc = queryCtx.matches[i];
          if (mtc.smoothIteration !== queryCtx.smoothi) continue;
          avgMatchValue += mtc.match;
          avgMatchValueCount++;
        }
        avgMatchValue = avgMatchValue / avgMatchValueCount;
        queryCtx.notOperatorVal = avgMatchValue * 1.2;
      } else {
        queryCtx.notOperatorVal = queryCtx.notOperator;
      }
      this.findNotMatches(dataSections, queryCtx);
    }
  };

  this.findNotMatches = function (dataSections, queryCtx) {
    var dsi, i, msi, currentSections = [];
    for (dsi = 0; dsi < dataSections.length; dsi++) {
      var sec = dataSections[dsi];
      for (i = 0; i < queryCtx.matches.length; i++) {
        var mtc = queryCtx.matches[i];
        if (mtc.smoothIteration !== queryCtx.smoothi) continue;
        if (mtc.match >= queryCtx.notOperatorVal) {
          continue;
        }
        for (msi = 0; msi < mtc.sections.length; msi++) {
          if (mtc.sections[msi] == sec) {
            dataSections[dsi] = null;
            break;
          }
        }
      }
    }

    var currentSINotMatches = [];
    for (dsi = 0; dsi < dataSections.length; dsi++) {
      if (dataSections[dsi] !== null) {
        currentSections.push(dataSections[dsi]);
      } else {
        if (currentSections.length > 0 && currentSections.length / dataSections.length < Parameters.NOT_OPERATOR_MAX_RELATIVE_LENGTH) {
          this.createNotMatch(currentSections, currentSINotMatches, queryCtx);
          currentSections.length = 0; // 清空数组
        }
      }
    }
    if (currentSections.length > 0 && currentSections.length / dataSections.length < Parameters.NOT_OPERATOR_MAX_RELATIVE_LENGTH) {
      this.createNotMatch(currentSections, currentSINotMatches, queryCtx);
      currentSections.length = 0; // 清空数组
    }

    for (i = 0; i < currentSINotMatches.length; i++) {
      currentSINotMatches[i].match = currentSINotMatches.length;
    }

  };

  this.createNotMatch = function (sections, currentSINotMatches, queryCtx) {
    var matchedPts = [];
    for (var si = 0; si < sections.length; si++) {
      for (var pi = 0; pi < sections[si].points.length; pi++) {
        matchedPts.push(sections[si].points[pi]);
      }
    }

    var newNotMatch = {
      id: queryCtx.notMatches.length,
      snum: queryCtx.snum,
      smoothIteration: queryCtx.smoothi,
      match: -1,
      size: (_.last(matchedPts).x - matchedPts[0].x) / queryCtx.datasetSize,
      timespan: this.calculateMatchTimeSpan(matchedPts[0], _.last(matchedPts)),
      points: matchedPts
    };

    queryCtx.notMatches.push(newNotMatch);
    currentSINotMatches.push(newNotMatch);
  };

  this.matchIn = function (currSect, dataSections, dsi, qSections, queryCtx, lastQuerySect) {
    if (qSections.length > Parameters.MAX_REGEX_IT) return false;
    var matchValue, i, sectsBlock = [currSect];

    while (currSect.next.length === 1 && currSect != lastQuerySect) {
      currSect = currSect.next[0].dest;
      sectsBlock.push(currSect);
    }

    if (dsi + sectsBlock.length + qSections.length > dataSections.length)
      return false; 

    if (qSections.length > 0) {
      var lastQSectionsSectPt = _.last(_.last(qSections).points), firstSectsBlockPt = sectsBlock[0].points[0];
      if (firstSectsBlockPt.x < lastQSectionsSectPt.x) {
        var offset = - firstSectsBlockPt.x + lastQSectionsSectPt.x;
        var offseto = - firstSectsBlockPt.origX + lastQSectionsSectPt.origX;
        for (i = 0; i < sectsBlock.length; i++) {
          sectsBlock[i] = sectsBlock[i].translateXCopy(offset, offseto);
        }
      }
    }
    var newQSections = qSections.concat(sectsBlock);


    var dataSectsForQ = dataSections.slice(dsi, dsi + newQSections.length);

    // 如果我们到达了查询的末尾，我们实际上可以使用它
    if (currSect == lastQuerySect &&
      (currSect.next.length === 0 || !currSect.next[0].size || currSect.next[0].size == currSect.next[0].times)) {
      matchValue = this.calculateMatch(dataSectsForQ, newQSections, queryCtx, false);
      if (matchValue !== null) {

        // 如果在不同的平滑迭代中选择了相同的区域，则仅保留一个（最佳）匹配
        var duplicateMatchIdx = Parameters.REMOVE_EQUAL_MATCHES ? this.searchEqualMatch(matchValue, queryCtx.matches) : -1;
        if (duplicateMatchIdx === -1) {
          matchValue.id = queryCtx.matches.length; // 新匹配的新 id
          queryCtx.matches.push(matchValue);
        } else if (queryCtx.matches[duplicateMatchIdx].match > matchValue.match) {
          matchValue.id = queryCtx.matches[duplicateMatchIdx].id; // 我们保留旧的匹配 id
          queryCtx.matches[duplicateMatchIdx] = matchValue;
        }

      }
    }

    if (currSect.next.length >= 1) {
      var backLink = false;
      for (i = currSect.next.length - 1; i >= 0; i--) { // 迭代重复和直链
        var next = currSect.next[i];
        if (currSect == lastQuerySect || i > 0) { // 这是一个回链
          if (!next.size) {
            this.matchIn(next.dest, dataSections, dsi, newQSections, queryCtx, lastQuerySect);
          } else if (next.times < next.size) {
            next.times++;
            backLink = true; // 仅在存在严格重复时排除直链
            this.matchIn(next.dest, dataSections, dsi, newQSections, queryCtx, lastQuerySect);
          }
        } else if (!backLink) {
          this.matchIn(next.dest, dataSections, dsi, newQSections, queryCtx, lastQuerySect);
        }
      }
    }

  };

  /**
   *
   * @param matchedSections
   * @param querySections
   * @param queryCtx
   * @param partialQuery 如果为 true，它将不返回有关匹配的任何信息，仅返回其匹配值。
   *                     使用部分查询时，也不会检查查询长度
   */
  this.calculateMatch = function (matchedSections, querySections, queryCtx, partialQuery) {
    var pointsMatchRes = this.calculatePointsMatch(querySections, matchedSections, partialQuery);
    if (pointsMatchRes === null) return null;
    if (pointsMatchRes.match > Parameters.MATCH_METRIC_MAXIMUM_VALUE) return null;
    if (!this.queryLengthStrictMode && partialQuery) return { match: pointsMatchRes.match };

    var matchedPts = pointsMatchRes.matchedPoints;
    var minPos = matchedPts[0].x;
    var maxPos = _.last(matchedPts).x;
    var matchSize = (maxPos - minPos) / queryCtx.datasetSize;
    var matchPos = ((maxPos + minPos) / 2) / queryCtx.datasetSize;
    var matchTimeSpan = this.calculateMatchTimeSpan(matchedPts[0], _.last(matchedPts));

    if (this.queryLengthStrictMode && !this.checkQueryLength(matchTimeSpan.value)) return null;

    if (this.queryHeight !== null) {
      if (!this.checkQueryHeight(this.calculateMatchHeight(matchedPts))) return null;
    }

    if (this.queryHorizontalOffset) {
      if (this.queryHorizontalOffset.min > 0) {
        if (matchedPts[0].origX < this.queryHorizontalOffset.min) return null;
      }

      if (this.queryHorizontalOffset.max > 0) {
        if (_.last(matchedPts).origX > this.queryHorizontalOffset.max) return null;
      }
    }

    if (this.queryVerticalOffset) {
      if (this.queryVerticalOffset.min > 0) {
        var minY = _.min(matchedPts, 'y').origY;
        if (minY < this.queryVerticalOffset.min) return null;
      }

      if (this.queryVerticalOffset.max > 0) {
        var maxY = _.max(matchedPts, 'y').origY;
        if (maxY > this.queryVerticalOffset.max) return null;
      }
    }


    if (partialQuery) return { match: pointsMatchRes.match };

    return {
      snum: queryCtx.snum,
      smoothIteration: queryCtx.smoothi,
      match: pointsMatchRes.match,
      size: matchSize,
      matchPos: matchPos,
      timespan: matchTimeSpan,
      points: matchedPts,
      minPos: minPos,
      maxPos: maxPos,
      sections: matchedSections,
      debugLines: pointsMatchRes.debugLines,
      errors: pointsMatchRes.errors
    };
  };

  /* 搜索查询兼容性。返回 false 表示查询与给定数据不兼容。 */
  this.areCompatibleSections = function (querySections, dataSections, checkLength) {
    if (querySections.length != dataSections.length) {
      // console.log('查询和数据部分大小不同');
      return false;
    }

    if (this.queryLength !== null && checkLength) {
      var lastDataSection = _.last(dataSections);
      var maxMatchLength = _.last(lastDataSection.points).origX - dataSections[0].points[0].origX +
        this.queryLength * this.queryLengthTolerance;
      var minMatchLength = (dataSections.length == 1 ? 0 : lastDataSection.points[0].origX - _.last(dataSections[0].points).origX) -
        this.queryLength * this.queryLengthTolerance;
      if (this.queryLength > maxMatchLength || this.queryLength < minMatchLength) return false;
    }

    var incompatibleSections = 0;
    for (var j = 0; j < querySections.length; j++) {
      if (querySections[j].sign !== 0 && querySections[j].sign != dataSections[j].sign) incompatibleSections++;
    }
    return incompatibleSections / querySections.length <= Parameters.QUERY_SIGN_MAXIMUM_TOLERABLE_DIFFERENT_SIGN_SECTIONS;
  };

  this.getBounds = function (sections, startSectIdx, endSectIdx) {
    if (sections === null) return null;
    var bounds = {
      minX: Number.MAX_SAFE_INTEGER, maxX: Number.MIN_SAFE_INTEGER,
      minY: Number.MAX_SAFE_INTEGER, maxY: Number.MIN_SAFE_INTEGER
    };
    bounds.minX = sections[startSectIdx].points[0].x;
    bounds.maxX = _.last(sections[endSectIdx].points).x;
    for (var i = startSectIdx; i < endSectIdx; i++) {
      var localMinY = _.min(sections[i].points, 'y').y;
      var localMaxY = _.max(sections[i].points, 'y').y;
      if (localMinY < bounds.minY) bounds.minY = localMinY;
      if (localMaxY > bounds.maxY) bounds.maxY = localMaxY;
    }
    return bounds;
  };

  // 将部分数量减少到 n，将最小的部分与最小的相邻部分合并
  this.reduceSections = function (sections, n) {
    var i;
    if (n >= sections.length || n < 1) return sections;
    // if (n < sections.length + 1) return null;
    var newSections = [];
    for (i = 0; i < sections.length; i++) newSections.push(sections[i].copy());

    while (n < newSections.length) {
      var smallestSection = null;
      var sectionSizeAvg = 0;
      for (i = 0; i < newSections.length; i++) {
        sectionSizeAvg += newSections[i].sizeEucl();
        if (smallestSection === null || newSections[smallestSection].sizeEucl() > newSections[i].sizeEucl()) {
          smallestSection = i;
        }
      }
      sectionSizeAvg /= newSections.length;
      if (newSections[smallestSection].sizeEucl() > sectionSizeAvg * 0.8) return null;

      if (smallestSection === 0) {
        newSections[smallestSection].concat(newSections[1]);
        newSections.splice(1, 1);
      } else if (smallestSection === newSections.length - 1) {
        newSections[newSections.length - 2].concat(newSections[newSections.length - 1]);
        newSections.splice(newSections.length - 1, 1);
      } else if (newSections[smallestSection - 1].sizeEucl() <= newSections[smallestSection + 1].sizeEucl()) {
        newSections[smallestSection - 1].concat(newSections[smallestSection]);
        newSections.splice(smallestSection, 1);
      } else {
        newSections[smallestSection].concat(newSections[smallestSection + 1]);
        newSections.splice(smallestSection + 1, 1);
      }
    }

    return newSections;
  };

  this.expandSections = function (sections, n) {
    var i;
    if (n <= sections.length) return sections;
    var newSections = [];
    for (i = 0; i < sections.length - 1; i++) newSections.push(sections[i]);

    for (i = sections.length; i <= n; i++) {
      newSections.push(sections[sections.length - 1].copy());
    }
    return newSections;
  };

  /* 计算匹配，考虑将给定部分与查询的所有部分进行比较。
   * 每个查询部分都被缩放以匹配参数的每个部分，并比较其切线。 */
  this.calculatePointsMatch = function (querySections, matchedSections, partialQuery) {
    var reduced = false, expanded = false;

    if (Parameters.CHECK_QUERY_COMPATIBILITY) {
      if (!this.areCompatibleSections(querySections, matchedSections, !partialQuery)) return null;
    } else {
      if (querySections.length > matchedSections.length) {
        matchedSections = this.expandSections(matchedSections, querySections.length);
        expanded = true;
      } else if (querySections.length < matchedSections.length) {
        matchedSections = this.reduceSections(matchedSections, querySections.length);
        reduced = true;
      }
      if (matchedSections == null) return null;
      if (!this.areCompatibleSections(querySections, matchedSections, !partialQuery)) return null;
    }

    var centroidsDifference;
    var i, si;

    var matchedSecBounds = this.getBounds(matchedSections,
      (matchedSections.length > 2 ? 1 : 0),
      matchedSections.length - (matchedSections.length > 2 ? 2 : 1)
    );

    var queryBounds = this.getBounds(querySections,
      (querySections.length > 2 ? 1 : 0),
      querySections.length - (querySections.length > 2 ? 2 : 1)
    );

    var subSequenceScaleFactorX = (matchedSecBounds.maxX - matchedSecBounds.minX) / (queryBounds.maxX - queryBounds.minX);
    var subSequenceScaleFactorY = (matchedSecBounds.maxY - matchedSecBounds.minY) / (queryBounds.maxY - queryBounds.minY);

    var debugLines = [];
    var pointDifferencesCost = 0;
    var rescalingCost = 0;
    var res;
    var matchedPoints = [];
    var errors = [];

    /* 然后它缩放所有部分并进行差异（缩放不会偏离平均缩放因子太远）*/
    for (si = 0; si < querySections.length; si++) {
      var dataSect = {}, querySect = {};
      res = {sum: 0, num: 0};

      querySect.points = querySections[si].points;
      querySect.width = _.last(querySect.points).x - querySect.points[0].x;
      querySect.height = _.max(querySect.points, 'y').y - _.min(querySect.points, 'y').y;
      if (querySect.height === 0) continue;

      if (si === 0 && querySections.length > 2 && Parameters.START_END_CUT_IN_SUBPARTS) {
        dataSect.points = this.sectionEndSubpartPoints(matchedSections[si], querySect.width * subSequenceScaleFactorX);
      } else if (si === querySections.length - 1 && querySections.length > 2 && Parameters.START_END_CUT_IN_SUBPARTS_IN_RESULTS) {
        dataSect.points = this.sectionStartSubpartPoints(matchedSections[si], querySect.width * subSequenceScaleFactorX);
      } else {
        dataSect.points = matchedSections[si].points;
      }

      dataSect.width = _.last(dataSect.points).x - dataSect.points[0].x;
      dataSect.height = _.max(dataSect.points, 'y').y - _.min(dataSect.points, 'y').y;
      if (dataSect.height === 0) continue;

      var scaleFactorX = dataSect.width / (querySect.width * subSequenceScaleFactorX);
      var scaleFactorY = dataSect.height / (querySect.height * (Parameters.RESCALING_Y ? subSequenceScaleFactorY : subSequenceScaleFactorX));

      if (scaleFactorX !== 0 && scaleFactorY !== 0)
        rescalingCost += Math.pow(Math.log(scaleFactorX), 2) + Math.pow(Math.log(scaleFactorY), 2);
      if (Parameters.DEBUG && !partialQuery) {
        errors.push({cx: Math.pow(Math.log(scaleFactorX), 2), cy: Math.pow(Math.log(scaleFactorY), 2)});
      }

      dataSect.centroidY = 0;
      for (i = 0; i < dataSect.points.length; i++) {
        dataSect.centroidY += dataSect.points[i].y;
      }
      dataSect.centroidY /= dataSect.points.length;
      querySect.centroidY = 0;
      for (i = 0; i < querySect.points.length; i++) {
        querySect.centroidY += querySect.points[i].y * (Parameters.RESCALING_Y ? subSequenceScaleFactorY : subSequenceScaleFactorX) * scaleFactorY;
      }
      querySect.centroidY /= querySect.points.length;
      centroidsDifference = querySect.centroidY - dataSect.centroidY;
      centroidsDifference = querySect.points[0].y * (Parameters.RESCALING_Y ? subSequenceScaleFactorY : subSequenceScaleFactorX) * scaleFactorY - dataSect.points[0].y;

      var queryPtsStep = querySect.points.length / dataSect.points.length;

      for (i = 0; i < dataSect.points.length; i++) {
        var dataPt = dataSect.points[i];
        var queryPt = querySect.points[Math.floor(i * queryPtsStep)];
        if (Parameters.DEBUG && !partialQuery) {
          debugLines.push({
            x1: dataPt.x,
            y1: queryPt.y * (Parameters.RESCALING_Y ? subSequenceScaleFactorY : subSequenceScaleFactorX) * scaleFactorY - centroidsDifference,
            x2: dataPt.x,
            y2: dataPt.y
          });
        }

        res.sum += math.abs((queryPt.y * (Parameters.RESCALING_Y ? subSequenceScaleFactorY : subSequenceScaleFactorX) * scaleFactorY - centroidsDifference) - dataPt.y) / dataSect.height;

        res.num++;
      }

      if (!partialQuery) {
        if (Parameters.START_END_CUT_IN_SUBPARTS_IN_RESULTS) {
          for (i = 0; i < dataSect.points.length; i++) matchedPoints.push(dataSect.points[i]);
        } else {
          for (i = 0; i < matchedSections[si].points.length; i++) matchedPoints.push(matchedSections[si].points[i]);
        }
      }

      // if (res.num > 0) pointDifferencesCost += math.sqrt(res.sum) / res.num;
      if (res.num > 0) pointDifferencesCost += res.sum / res.num;
    }

    // 结果定义为曲线之间的平均归一化差异
    return {
      match: pointDifferencesCost * Parameters.VALUE_DIFFERENCE_WEIGHT + rescalingCost * Parameters.RESCALING_COST_WEIGHT,
      matchedPoints: matchedPoints,
      debugLines: debugLines, // 用于调试
      errors: errors, // 用于调试
      reduced: reduced, // 用于调试
      expanded: expanded // 用于调试
    };
  };

  this.sectionStartSubpartPoints = function (section, width) {
    var startX = section.points[0].x, points = [];
    for (var pi = 0; pi < section.points.length; pi++) {
      points.push(section.points[pi]);
      if (section.points[pi].x - startX >= width) break;
    }
    return points;
  };

  this.sectionEndSubpartPoints = function (section, width) {
    var endX = _.last(section.points).x, points = [];
    for (var pi = section.points.length - 1; pi >= 0; pi--) {
      points.unshift(section.points[pi]);
      if (endX - section.points[pi].x >= width) break;
    }
    return points;
  };


  /* 返回与 targetMatch 起始和结束位置相同的匹配的索引，如果未找到则返回 -1。 */
  this.searchEqualMatch = function (targetMatch, matches) {
    var targetStartX = targetMatch.points[0].x,
      targetEndX = _.last(targetMatch.points).x;
    for (var idx = 0; idx < matches.length; idx++) {
      if (Math.abs(targetStartX - matches[idx].points[0].x) <= 10 &&
        Math.abs(targetEndX - _.last(matches[idx].points).x) <= 10) {
        return idx;
      }
    }
    return -1;
  };


  /**
   * 计算两个序列之间的欧几里得距离
   * 由于 series1 和 series2 的 x 值相同（它们应该是具有相同元素数量的两个时间序列），
   * 欧几里得距离公式可以简化为绝对差。
   *
   * relativeheight 仅由欧几里得距离使用（与 Qetch 部分分区一起使用）
   */
  this.euclideanDistance = function (series1, series2, relativeHeight) {
    if (relativeHeight === undefined) relativeHeight = 1;
    var res = 0;
    for (var i = 0; i < series1.length; i++) {
      res += Math.pow((series1[i] - series2[i]) / relativeHeight, 2);
    }
    return Math.sqrt(res);
  };

  /**
   * 在 DTW 或 ED（查询长度版本）中执行查询
   */
  this.executeQueryVDTWorVED = function () {
    var startingTime = new Date();

    var matches = [];
    var j, i, pi;
    var queryValues = [];

    for (var datasetIdx = 0; datasetIdx < DatasetAPI.getDatasetsNum(); datasetIdx++) {
      var dataPoints = DatasetAPI.getData(datasetIdx, 0); // 仅平滑 0，DTW 可以处理噪声

      var dataStep = (_.last(dataPoints).origX - dataPoints[0].origX) / dataPoints.length;

      var queryLength = Math.ceil(this.queryLength / dataStep);

      // 查询采样以适应与数据集相同的大小（重新插值）
      var groupSize = Math.ceil(this.points.length / queryLength);
      var acc = 0, accc = 0;
      for (i = 0; i < this.points.length; i++) {
        acc += this.points[i].y;
        accc++;
        if ((i + 1) % groupSize === 0) {
          queryValues.push(acc / accc);
          acc = accc = 0;
        }
      }

      // 计算查询 y 平均值
      var queryAvgY = math.mean(queryValues);

      // 计算具有该查询大小的子序列的数据集宽度
      var queryWidth = _.last(this.points).x - this.points[0].x;
      var queryHeight = _.max(this.points, 'y').y - _.min(this.points, 'y').y;
      var slidingWindowStep = Math.ceil(queryLength / 100) * Parameters.QUERYLENGTH_SLIDING_WINDOW_STEP;

      // 通过数据滑动窗口以查找匹配项
      for (i = 0; i < dataPoints.length - queryLength - 1; i += slidingWindowStep) {
        var subSequencePoints = [];
        var subSequenceValues = [];
        for (j = 0; j < queryLength; j++) {
          subSequencePoints.push(dataPoints[i + j]);
          subSequenceValues.push(dataPoints[i + j].y);
        }

        var datasetQuerySizeWidth = subSequencePoints[subSequencePoints.length - 1].x - subSequencePoints[0].x;
        var datasetQuerySizeHeight = _.max(subSequenceValues) - _.min(subSequenceValues);
        var scaleFactorX = queryWidth / datasetQuerySizeWidth;
        var scaleFactorY = queryHeight / datasetQuerySizeHeight;

        for (j = 0; j < subSequenceValues.length; j++) {
          subSequenceValues[j] *= Parameters.RESCALING_Y ? scaleFactorY : scaleFactorX;
        }

        // 计算数据集子部分的中心点（这些是重新缩放的点，因此我们不需要乘以
        // datasetAvgY 乘以缩放因子）
        var datasetAvgY = math.mean(subSequenceValues);

        // 偏移平移（将数据集的子部分移动到与查询相同的高度）
        var datasetQueryDifference = queryAvgY - datasetAvgY;
        for (j = 0; j < subSequenceValues.length; j++) subSequenceValues[j] += datasetQueryDifference;

        var cost;
        if (Parameters.ALGORITHM_TO_USE == 'dtw') {
          cost = new DTW().compute(queryValues, subSequenceValues);
        } else {
          cost = this.euclideanDistance(queryValues, subSequenceValues, queryHeight);
        }

        var matchTimeSpan = this.calculateMatchTimeSpan(subSequencePoints[0], _.last(subSequencePoints));
        var minPos = subSequencePoints[0].x;
        var maxPos = _.last(subSequencePoints).x;

        var newMatch = {
          snum: datasetIdx,
          id: matches.length,
          smoothIteration: 0,
          match: cost,
          timespan: matchTimeSpan,
          size: this.queryLength,
          points: subSequencePoints,
          minPos: minPos,
          maxPos: maxPos
        };
        matches.push(newMatch);
      }
    }

    var finishingTime = new Date();
    Qetch.DEBUG_LAST_EXECUTING_TIME = finishingTime - startingTime;

    return matches;
  };

  /* 用于 1NN */
  this.calculateDTWorED = function (queryPoints, dataPoints, alg) {
    var datasetPtsStep = dataPoints.length / queryPoints.length;

    var datasetValues = [];
    for (var i = 0; i < queryPoints.length; i++) {
      var dataPt = dataPoints[Math.floor(i * datasetPtsStep)];
      datasetValues.push(dataPt.y);
    }

    var queryValues = [];
    for (i = 0; i < queryPoints.length; i++) queryValues.push(queryPoints[i].y);

    // 计算具有该查询大小的子序列的数据集宽度
    var queryWidth = _.last(queryPoints).x - queryPoints[0].x;
    var queryHeight = _.max(queryPoints, 'y').y - _.min(queryPoints, 'y').y;

    // 计算数据集 y 平均值
    var queryAvgY = 0;
    for (i = 0; i < queryPoints.length; i++) queryAvgY += queryValues[i];
    queryAvgY /= queryPoints.length;

    // 计算具有该查询大小的子序列的数据集宽度
    var dsWidth = _.last(dataPoints).x - dataPoints[0].x;
    var dsHeight = _.max(dataPoints, 'y').y - _.min(dataPoints, 'y').y;

    var scaleFactorY = queryHeight / dsHeight;

    for (var j = 0; j < datasetValues.length; j++) {
      datasetValues[j] *= scaleFactorY;
    }

    // 计算数据集子部分的中心点（这些是重新缩放的点，因此我们不需要乘以
    // datasetAvgY 乘以缩放因子）
    var datasetAvgY = 0;
    for (j = 0; j < datasetValues.length; j++) datasetAvgY += datasetValues[j];
    datasetAvgY /= datasetValues.length;

    // 将数据集的子部分移动到与查询相同的幅度
    var datasetQueryDifference = queryAvgY - datasetAvgY;
    for (j = 0; j < datasetValues.length; j++) datasetValues[j] += datasetQueryDifference;

    var cost;
    if (alg == 'dtw') {
      cost = new DTW().compute(queryValues, datasetValues);
    } else {
      cost = this.euclideanDistance(queryValues, datasetValues);
    }

    return {match: cost};
  };

  this.checkQueryLength = function (queryLength) {
    if (this.queryLength === null) return true;
    var min = this.queryLength - this.queryLength * this.queryLengthTolerance;
    var max = this.queryLength + this.queryLength * this.queryLengthTolerance;
    // console.log('查询长度: ', queryLength, ' 最小: ', min, ' 最大: ', max, ' 结果: ', queryLength >= min && queryLength <= max);
    return queryLength >= min && queryLength <= max;
  };

  this.checkQueryHeight = function (queryHeight) {
    if (this.queryHeight === null) return true;
    var min = this.queryHeight - this.queryHeight * this.queryHeightTolerance;
    var max = this.queryHeight + this.queryHeight * this.queryHeightTolerance;
    console.log('查询高度: ', queryHeight, ' 最小: ', min, ' 最大: ', max, ' 结果: ', queryHeight >= min && queryHeight <= max);
    return queryHeight >= min && queryHeight <= max;
  };

  this.extractPointsFromSections = function (sections) {
    var points = [];
    _.forEach(sections, function (section) {
      _.forEach(section.points, function (p) {
        points.push(p.copy());
      });
    });
    return points;
  };

  this.tangent = function (p1, p2) {
    return (p2.y - p1.y) / (p2.x - p1.x);
  };

  /**
   * 提取一组点的切线
   * @return *[] 切线数组：
   * 第一个切线与第一个和第二个点相关
   * 第二个与第二个和第一个相关
   * 第三个与第三个和第二个相关
   * ...
   */
  this.extractTangents = function (points) {
    if (points.length < 2) return [];
    var tangents = [this.tangent(points[0], points[1])];
    for (var i = 1; i < points.length; i++) {
      tangents.push(this.tangent(points[i - 1], points[i]));
    }
    return tangents;
  };

  /**
   * 给定一组切线，它将切线列表划分为一组部分。
   * 每个部分共享相同的切线符号（一个部分可以是增加的曲线
   * 或减少的曲线，但不能同时是两者）
   *
   * @return 部分数组。
   */
  this.findCurveSections = function (tangents, points, minHeightPerc) {
    var i, sign, sections = [], lastTg = null, lastPt = null;
    var totalHeight = _.max(points, 'y').y - _.min(points, 'y').y;
    var lastSect = null, lastSectHeight = 0;

    for (i = 0; i < tangents.length; i++) {
      var tangent = tangents[i], pt = points[i];
      sign = Math.sign(tangent);

      if (sections.length === 0) {
        sections.push(new Qetch.Section(sign));
      } else if (sign !== 0) {
        lastSect = _.last(sections);
        if (lastSect.sign != sign) {
          lastSectHeight = _.max(lastSect.points, 'y').y - _.min(lastSect.points, 'y').y;
          if (lastSect.points.length > 1 && (minHeightPerc > 0 ? lastSectHeight / totalHeight > minHeightPerc : true)) {
            var newSection = new Qetch.Section(sign);
            sections.push(newSection);
            newSection.points.push(lastPt);
            newSection.tangents.push(lastTg);  
          }
        }
      }

      lastSect = _.last(sections);
      lastSect.points.push(pt);
      lastSect.tangents.push(tangent);
      lastTg = tangent;
      lastPt = pt;
    }

    var count = 0;
    var prev = null;
    _.forEach(sections, function (s) {
      s.id = count++;
      if (prev !== null) prev.next.push({dest: s});
      prev = s;
    });
    prev.next = [];

    return sections;
  };

  /* 为正则表达式选择进行选择。此函数将分析当前查询
   以包括封闭的部分，并将返回一个 {x1: -, x2: -, y1: -, y2: -} 的矩形
   格式与输入的相同。
   */
  this.regexpOpSel = function (selRect, op) {
    var res = {x1: undefined, x2: undefined, y1: undefined, y2: undefined};
    var i, j, si, p;

    var startSelectedSectionIdx = null, endSelectedSectionIdx = null;
    for (i = 0; i < this.sections.length; i++) {
      var section = this.sections[i];
      for (j = 0; j < section.points.length; j++) {
        p = section.points[j];
        if (p.x >= selRect.x1 && p.x <= selRect.x2 && p.y <= selRect.y1 && p.y >= selRect.y2) {
          if (startSelectedSectionIdx === null) startSelectedSectionIdx = i;
          endSelectedSectionIdx = i;
          break;
        }
      }
    }
    if (startSelectedSectionIdx === null || endSelectedSectionIdx === null) return null;

    if (this.sections[startSelectedSectionIdx].sign == this.sections[endSelectedSectionIdx].sign) {
      endSelectedSectionIdx--;
    }
    if (endSelectedSectionIdx - startSelectedSectionIdx <= 0) return null;

    if (op.op === '+') {

      // 检查循环 
      for (i = startSelectedSectionIdx; i <= endSelectedSectionIdx; i++) {
        if (this.sections[i].next.length > 1) {
          console.log('发现循环，取消当前选择');
          return null;
        }
        for (si = endSelectedSectionIdx; si < this.sections.length; si++) {
          for (j = 0; j < this.sections[si].next.length; j++) {
            if (this.sections[si].next[j].dest.id == this.sections[i].id) {
              console.log('发现循环，取消当前选择');
              return null;
            }
          }
        }
      }

      this.sections[endSelectedSectionIdx].next.push({
        dest: this.sections[startSelectedSectionIdx],
        size: op.size
      });
    } else {
      // ...
    }

    for (i = startSelectedSectionIdx; i <= endSelectedSectionIdx; i++) {
      var sectionPts = this.sections[i].points;
      for (j = 0; j < sectionPts.length; j++) {
        p = sectionPts[j];
        if (res.x1 === undefined || res.x1 > p.x) res.x1 = p.x - 3; // + 一个常数
        if (res.x2 === undefined || res.x2 < p.x) res.x2 = p.x + 6; // 以获得填充
        if (res.y1 === undefined || res.y1 > p.y) res.y1 = p.y - 3;
        if (res.y2 === undefined || res.y2 < p.y) res.y2 = p.y + 6;
      }
    }

    return res;
  };
  this.setNotOperator = function (value) {
    this.notOperator = value;
  };
  this.resetRegexpOps = function () {
    this.notOperator = -1;
    var prev = null;
    _.forEach(this.sections, function (s) {
      if (prev !== null) prev.next = [{dest: s}];
      prev = s;
    });
    if (prev !== null) prev.next = [];
  };

  this.calculateMatchTimeSpan = function (startPoint, endPoint) {
    var matchTimeSpan = {
      value: endPoint.origX - startPoint.origX
    };

    if (matchTimeSpan.value < 1000) {
      matchTimeSpan.str = Math.round(matchTimeSpan.value) + ' 毫秒';
    } else if (matchTimeSpan.value < (1000 * 60)) {
      matchTimeSpan.str = (matchTimeSpan.value / 1000).toFixed(3) + ' 秒';
    } else if (matchTimeSpan.value < (1000 * 3600)) {
      matchTimeSpan.str = (matchTimeSpan.value / (1000 * 60)).toFixed(3) + ' 分钟';
    } else if (matchTimeSpan.value < (1000 * 3600 * 24)) {
      matchTimeSpan.str = Math.round(matchTimeSpan.value / (1000 * 3600)) + ' 小时';
    } else if (matchTimeSpan.value < (1000 * 3600 * 24 * 365)) {
      matchTimeSpan.str = Math.round(matchTimeSpan.value / (1000 * 3600 * 24)) + ' 天';
    } else {
      matchTimeSpan.str = parseFloat(Math.round((matchTimeSpan.value / (1000 * 3600 * 24 * 365)) * 100) / 100).toFixed(1) + ' 年';
    }

    return matchTimeSpan;
  };

  this.calculateMatchHeight = function (matchedPts) {
    var minY = _.min(matchedPts, 'y').origY;
    var maxY = _.max(matchedPts, 'y').origY;
    return maxY - minY;
  };

  document.getNumberOfSections = function (snum, smoothi) {
    var dataPoints = DatasetAPI.getData(snum, smoothi);
    var dataTangents = self.extractTangents(dataPoints);
    var dataSections = self.findCurveSections(dataTangents, dataPoints, Parameters.DIVIDE_SECTION_MIN_HEIGHT_DATA);
    return dataSections.length;
  };


}]);